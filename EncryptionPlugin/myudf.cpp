/*
** example file of UDF (user definable functions) that are dynamicly loaded
** into the standard mysqld core.
**
** The functions name, type and shared library is saved in the new system
** table 'func'.  To be able to create new functions one must have write
** privilege for the database 'mysql'.	If one starts MySQL with
** --skip-grant-tables, then UDF initialization will also be skipped.
**
** Syntax for the new commands are:
** create function <function_name> returns {string|real|integer}
**		  soname <name_of_shared_library>
** drop function <function_name>
**
** Each defined function may have a xxxx_init function and a xxxx_deinit
** function.  The init function should alloc memory for the function
** and tell the main function about the max length of the result
** (for string functions), number of decimals (for double functions) and
** if the result may be a null value.
**
** If a function sets the 'error' argument to 1 the function will not be
** called anymore and mysqld will return NULL for all calls to this copy
** of the function.
**
** All strings arguments to functions are given as string pointer + length
** to allow handling of binary data.
** Remember that all functions must be thread safe. This means that one is not
** allowed to alloc any global or static variables that changes!
** If one needs memory one should alloc this in the init function and free
** this on the __deinit function.
**
** Note that the init and __deinit functions are only called once per
** SQL statement while the value function may be called many times
**
** Function 'metaphon' returns a metaphon string of the string argument.
** This is something like a soundex string, but it's more tuned for English.
**
** Function 'myfunc_double' returns summary of codes of all letters
** of arguments divided by summary length of all its arguments.
**
** Function 'myfunc_int' returns summary length of all its arguments.
**
** Function 'sequence' returns an sequence starting from a certain number.
**
** Function 'myfunc_argument_name' returns name of argument.
**
** On the end is a couple of functions that converts hostnames to ip and
** vice versa.
**
** A dynamicly loadable file should be compiled shared.
** (something like: gcc -shared -o my_func.so myfunc.cc).
** You can easily get all switches right by doing:
** cd sql ; make udf_example.o
** Take the compile line that make writes, remove the '-c' near the end of
** the line and add -shared -o udf_example.so to the end of the compile line.
** The resulting library (udf_example.so) should be copied to some dir
** searched by ld. (/usr/lib ?)
** If you are using gcc, then you should be able to create the udf_example.so
** by simply doing 'make udf_example.so'.
**
** After the library is made one must notify mysqld about the new
** functions with the commands:
**
** CREATE FUNCTION metaphon RETURNS STRING SONAME "udf_example.so";
** CREATE FUNCTION myfunc_double RETURNS REAL SONAME "udf_example.so";
** CREATE FUNCTION myfunc_int RETURNS INTEGER SONAME "udf_example.so";
** CREATE FUNCTION sequence RETURNS INTEGER SONAME "udf_example.so";
** CREATE FUNCTION lookup RETURNS STRING SONAME "udf_example.so";
** CREATE FUNCTION reverse_lookup RETURNS STRING SONAME "udf_example.so";
** CREATE AGGREGATE FUNCTION avgcost RETURNS REAL SONAME "udf_example.so";
** CREATE FUNCTION myfunc_argument_name RETURNS STRING SONAME "udf_example.so";
**
** After this the functions will work exactly like native MySQL functions.
** Functions should be created only once.
**
** The functions can be deleted by:
**
** DROP FUNCTION metaphon;
** DROP FUNCTION myfunc_double;
** DROP FUNCTION myfunc_int;
** DROP FUNCTION lookup;
** DROP FUNCTION reverse_lookup;
** DROP FUNCTION avgcost;
** DROP FUNCTION myfunc_argument_name;
**
** The CREATE FUNCTION and DROP FUNCTION update the func@mysql table. All
** Active function will be reloaded on every restart of server
** (if --skip-grant-tables is not given)
**
** If you ge problems with undefined symbols when loading the shared
** library, you should verify that mysqld is compiled with the -rdynamic
** option.
**
** If you can't get AGGREGATES to work, check that you have the column
** 'type' in the mysql.func table.  If not, run 'mysql_upgrade'.
**
*/

#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <algorithm>
#include <mutex>
#include <new>
#include <regex>
#include <string>
#include <vector>
#include <windows.h>
#include <fstream>

#include "sm4.h"
#include "mysql.h"  // IWYU pragma: keep
#include "mysql/udf_registration_types.h"

#ifdef _WIN32
/* inet_aton needs winsock library */
#pragma comment(lib, "ws2_32")
#endif

/*
  Not all platforms have gethostbyaddr_r, so we use a global lock here instead.
  Production-quality code should use getaddrinfo where available.
*/
static std::mutex *LOCK_hostname{nullptr};

/* All function signatures must be right or mysqld will not find the symbol! */
using namespace std;


//sm4_algorithm_start #############################################
extern "C" {
/*
 * 32-bit integer manipulation macros (big endian)
 */
#ifndef GET_ULONG_BE
#define GET_ULONG_BE(n,b,i)                             \
{                                                       \
    (n) = ( (unsigned long) (b)[(i)    ] << 24 )        \
        | ( (unsigned long) (b)[(i) + 1] << 16 )        \
        | ( (unsigned long) (b)[(i) + 2] <<  8 )        \
        | ( (unsigned long) (b)[(i) + 3]       );       \
}
#endif

#ifndef PUT_ULONG_BE
#define PUT_ULONG_BE(n,b,i)                             \
{                                                       \
    (b)[(i)    ] = (unsigned char) ( (n) >> 24 );       \
    (b)[(i) + 1] = (unsigned char) ( (n) >> 16 );       \
    (b)[(i) + 2] = (unsigned char) ( (n) >>  8 );       \
    (b)[(i) + 3] = (unsigned char) ( (n)       );       \
}
#endif

 /*
  *rotate shift left marco definition
  *
  */
#define  SHL(x,n) (((x) & 0xFFFFFFFF) << n)
#define ROTL(x,n) (SHL((x),n) | ((x) >> (32 - n)))

#define SWAP(a,b) { unsigned long t = a; a = b; b = t; t = 0; }

  /*
   * Expanded SM4 S-boxes
   /* Sbox table: 8bits input convert to 8 bits output*/

    static const unsigned char SboxTable[16][16] =
    {
            {0xd6,0x90,0xe9,0xfe,0xcc,0xe1,0x3d,0xb7,0x16,0xb6,0x14,0xc2,0x28,0xfb,0x2c,0x05},
            {0x2b,0x67,0x9a,0x76,0x2a,0xbe,0x04,0xc3,0xaa,0x44,0x13,0x26,0x49,0x86,0x06,0x99},
            {0x9c,0x42,0x50,0xf4,0x91,0xef,0x98,0x7a,0x33,0x54,0x0b,0x43,0xed,0xcf,0xac,0x62},
            {0xe4,0xb3,0x1c,0xa9,0xc9,0x08,0xe8,0x95,0x80,0xdf,0x94,0xfa,0x75,0x8f,0x3f,0xa6},
            {0x47,0x07,0xa7,0xfc,0xf3,0x73,0x17,0xba,0x83,0x59,0x3c,0x19,0xe6,0x85,0x4f,0xa8},
            {0x68,0x6b,0x81,0xb2,0x71,0x64,0xda,0x8b,0xf8,0xeb,0x0f,0x4b,0x70,0x56,0x9d,0x35},
            {0x1e,0x24,0x0e,0x5e,0x63,0x58,0xd1,0xa2,0x25,0x22,0x7c,0x3b,0x01,0x21,0x78,0x87},
            {0xd4,0x00,0x46,0x57,0x9f,0xd3,0x27,0x52,0x4c,0x36,0x02,0xe7,0xa0,0xc4,0xc8,0x9e},
            {0xea,0xbf,0x8a,0xd2,0x40,0xc7,0x38,0xb5,0xa3,0xf7,0xf2,0xce,0xf9,0x61,0x15,0xa1},
            {0xe0,0xae,0x5d,0xa4,0x9b,0x34,0x1a,0x55,0xad,0x93,0x32,0x30,0xf5,0x8c,0xb1,0xe3},
            {0x1d,0xf6,0xe2,0x2e,0x82,0x66,0xca,0x60,0xc0,0x29,0x23,0xab,0x0d,0x53,0x4e,0x6f},
            {0xd5,0xdb,0x37,0x45,0xde,0xfd,0x8e,0x2f,0x03,0xff,0x6a,0x72,0x6d,0x6c,0x5b,0x51},
            {0x8d,0x1b,0xaf,0x92,0xbb,0xdd,0xbc,0x7f,0x11,0xd9,0x5c,0x41,0x1f,0x10,0x5a,0xd8},
            {0x0a,0xc1,0x31,0x88,0xa5,0xcd,0x7b,0xbd,0x2d,0x74,0xd0,0x12,0xb8,0xe5,0xb4,0xb0},
            {0x89,0x69,0x97,0x4a,0x0c,0x96,0x77,0x7e,0x65,0xb9,0xf1,0x09,0xc5,0x6e,0xc6,0x84},
            {0x18,0xf0,0x7d,0xec,0x3a,0xdc,0x4d,0x20,0x79,0xee,0x5f,0x3e,0xd7,0xcb,0x39,0x48}
    };

    /* System parameter */
    static const unsigned long FK[4] = { 0xa3b1bac6,0x56aa3350,0x677d9197,0xb27022dc };

    /* fixed parameter */
    static const unsigned long CK[32] =
    {
            0x00070e15,0x1c232a31,0x383f464d,0x545b6269,
            0x70777e85,0x8c939aa1,0xa8afb6bd,0xc4cbd2d9,
            0xe0e7eef5,0xfc030a11,0x181f262d,0x343b4249,
            0x50575e65,0x6c737a81,0x888f969d,0xa4abb2b9,
            0xc0c7ced5,0xdce3eaf1,0xf8ff060d,0x141b2229,
            0x30373e45,0x4c535a61,0x686f767d,0x848b9299,
            0xa0a7aeb5,0xbcc3cad1,0xd8dfe6ed,0xf4fb0209,
            0x10171e25,0x2c333a41,0x484f565d,0x646b7279
    };


    /*
     * private function:
     * look up in SboxTable and get the related value.
     * args:    [in] inch: 0x00~0xFF (8 bits unsigned value).
     */
    static unsigned char sm4Sbox(unsigned char inch)
    {
        unsigned char* pTable = (unsigned char*)SboxTable;
        unsigned char retVal = (unsigned char)(pTable[inch]);
        return retVal;
    }

    /*
     * private F(Lt) function:
     * "T algorithm" == "L algorithm" + "t algorithm".
     * args:    [in] a: a is a 32 bits unsigned value;
     * return: c: c is calculated with line algorithm "L" and nonline algorithm "t"
     */
    static unsigned long sm4Lt(unsigned long ka)
    {
        unsigned long bb = 0;
        unsigned long c = 0;
        unsigned char a[4];
        unsigned char b[4];
        PUT_ULONG_BE(ka, a, 0)
            b[0] = sm4Sbox(a[0]);
        b[1] = sm4Sbox(a[1]);
        b[2] = sm4Sbox(a[2]);
        b[3] = sm4Sbox(a[3]);
        GET_ULONG_BE(bb, b, 0)
            c = bb ^ (ROTL(bb, 2)) ^ (ROTL(bb, 10)) ^ (ROTL(bb, 18)) ^ (ROTL(bb, 24));
        return c;
    }

    /*
     * private F function:
     * Calculating and getting encryption/decryption contents.
     * args:    [in] x0: original contents;
     * args:    [in] x1: original contents;
     * args:    [in] x2: original contents;
     * args:    [in] x3: original contents;
     * args:    [in] rk: encryption/decryption key;
     * return the contents of encryption/decryption contents.
     */
    static unsigned long sm4F(unsigned long x0, unsigned long x1, unsigned long x2, unsigned long x3, unsigned long rk)
    {
        return (x0 ^ sm4Lt(x1 ^ x2 ^ x3 ^ rk));
    }


    /* private function:
     * Calculating round encryption key.
     * args:    [in] a: a is a 32 bits unsigned value;
     * return: sk[i]: i{0,1,2,3,...31}.
     */
    static unsigned long sm4CalciRK(unsigned long ka)
    {
        unsigned long bb = 0;
        unsigned long rk = 0;
        unsigned char a[4];
        unsigned char b[4];
        PUT_ULONG_BE(ka, a, 0)
            b[0] = sm4Sbox(a[0]);
        b[1] = sm4Sbox(a[1]);
        b[2] = sm4Sbox(a[2]);
        b[3] = sm4Sbox(a[3]);
        GET_ULONG_BE(bb, b, 0)
            rk = bb ^ (ROTL(bb, 13)) ^ (ROTL(bb, 23));
        return rk;
    }

    static void sm4_setkey(unsigned long SK[32], unsigned char key[16])
    {
        unsigned long MK[4];
        unsigned long k[36];
        unsigned long i = 0;

        GET_ULONG_BE(MK[0], key, 0);
        GET_ULONG_BE(MK[1], key, 4);
        GET_ULONG_BE(MK[2], key, 8);
        GET_ULONG_BE(MK[3], key, 12);
        k[0] = MK[0] ^ FK[0];
        k[1] = MK[1] ^ FK[1];
        k[2] = MK[2] ^ FK[2];
        k[3] = MK[3] ^ FK[3];
        for (; i < 32; i++)
        {
            k[i + 4] = k[i] ^ (sm4CalciRK(k[i + 1] ^ k[i + 2] ^ k[i + 3] ^ CK[i]));
            SK[i] = k[i + 4];
        }

    }

    /*
     * SM4 standard one round processing
     *
     */
    static void sm4_one_round(unsigned long sk[32],
        unsigned char input[16],
        unsigned char output[16])
    {
        unsigned long i = 0;
        unsigned long ulbuf[36];

        //memset(ulbuf, 0, sizeof(ulbuf));
        GET_ULONG_BE(ulbuf[0], input, 0)
            GET_ULONG_BE(ulbuf[1], input, 4)
            GET_ULONG_BE(ulbuf[2], input, 8)
            GET_ULONG_BE(ulbuf[3], input, 12)
            while (i < 32)
            {
                ulbuf[i + 4] = sm4F(ulbuf[i], ulbuf[i + 1], ulbuf[i + 2], ulbuf[i + 3], sk[i]);
                // #ifdef _DEBUG
                //        	printf("rk(%02d) = 0x%08x,  X(%02d) = 0x%08x \n",i,sk[i], i, ulbuf[i+4] );
                // #endif
                i++;
            }
        PUT_ULONG_BE(ulbuf[35], output, 0);
        PUT_ULONG_BE(ulbuf[34], output, 4);
        PUT_ULONG_BE(ulbuf[33], output, 8);
        PUT_ULONG_BE(ulbuf[32], output, 12);
    }

    /*
     * SM4 key schedule (128-bit, encryption)
     */
    void sm4_setkey_enc(sm4_context* ctx, unsigned char key[16])
    {
        ctx->mode = SM4_ENCRYPT;
        sm4_setkey(ctx->sk, key);
    }

    /*
     * SM4 key schedule (128-bit, decryption)
     */
    void sm4_setkey_dec(sm4_context* ctx, unsigned char key[16])
    {
        int i;
        ctx->mode = SM4_ENCRYPT;
        sm4_setkey(ctx->sk, key);
        for (i = 0; i < 16; i++)
        {
            SWAP(ctx->sk[i], ctx->sk[31 - i]);
        }
    }


    /*
     * SM4-ECB block encryption/decryption
     */

    void sm4_crypt_ecb(sm4_context* ctx,
        int mode,
        int length,
        unsigned char* input,
        unsigned char* output)
    {
        while (length > 0)
        {
            sm4_one_round(ctx->sk, input, output);
            input += 16;
            output += 16;
            length -= 16;
        }

    }

    void PKCS7(unsigned char* pucData, unsigned long ulDataLen, unsigned char pucPaddingData[16])
    {
        unsigned char pucPadding = 0;
        pucPadding = 16 - (unsigned char)ulDataLen;

        memcpy(pucPaddingData, pucData, ulDataLen);
        memset(pucPaddingData + ulDataLen, pucPadding, 16 - ulDataLen);
    }

    /*
     * SM4-CBC buffer encryption/decryption
     */
    void sm4_crypt_cbc(sm4_context* ctx,
        int mode,
        int length,
        unsigned char* input,
        unsigned char* output)
    {
        int i;
        unsigned char iv[16] = { 0x25,0xaf,0x65,0x4b,0x34,0xea,0xdf,0xa6,0x84,0xc4,0x59,0x59,0x7b,0x6e,0xff,0xcc };
        unsigned char temp[16];

        if (mode == SM4_ENCRYPT)
        {
            while (length > 0)
            {
                if (length < 16) {
                    PKCS7(input, length, temp);
                    for (i = 0; i < 16; i++)
                        output[i] = (unsigned char)(temp[i] ^ iv[i]);
                }
                else {
                    for (i = 0; i < 16; i++)
                        output[i] = (unsigned char)(input[i] ^ iv[i]);
                }

                sm4_one_round(ctx->sk, output, output);
                memcpy(iv, output, 16);

                input += 16;
                output += 16;
                length -= 16;
            }
        }
        else /* SM4_DECRYPT */
        {
            while (length > 0)
            {
                memcpy(temp, input, 16);
                sm4_one_round(ctx->sk, input, output);

                for (i = 0; i < 16; i++)
                    output[i] = (unsigned char)(output[i] ^ iv[i]);

                memcpy(iv, temp, 16);

                input += 16;
                output += 16;
                length -= 16;
            }
        }
    }
    /*convert hex string to byte data*/
    void hex2byte(unsigned char* dst, unsigned char* src) {
        int i = 16;
        while (i--) {
            sscanf(reinterpret_cast<const char*>(src), "%02X", dst);
            src += 2;
            dst++;
        }
    }
    //sm4_algorithm_end #################################################
}

extern  "C++"  string get_key() {
    string filename;
    int DSLength = GetLogicalDriveStrings(0, NULL);
    //通过GetLogicalDriveStrings()函数获取所有驱动器字符串信息长度。
    char* DStr = new char[DSLength]; //用获取的长度在堆区创建一个c风格的字符串数组
    GetLogicalDriveStrings(DSLength, (LPTSTR)DStr);
    //通过GetLogicalDriveStrings将字符串信息复制到堆区数组中,其中保存了所有驱动器的信息。
    int DType;
    int si = 0;
    for (int i = 0; i < DSLength / 4; ++i)
        //为了显示每个驱动器的状态，则通过循环输出实现，由于DStr内部保存的数据是A:\NULLB:\NULLC:\NULL，这样的信息，所以DSLength/4可以获得具体大循环范围
    {
        char dir[12] = { DStr[si], ':', '\\' };
        DType = GetDriveType(DStr + i * 4);
        //GetDriveType函数，可以获取驱动器类型，参数为驱动器的根目录
        if (DType == DRIVE_REMOVABLE) {
            // cout << "可移动式磁盘:"<<dir<<endl;
            strcat_s(dir, "\\key.key");
            filename = dir;
        }
        si += 4;
    }
    if (filename.empty())
        return "NULL";
    else {
        string key;
        ifstream infile;
        infile.open(filename);
        infile >> key;
        //char* res = (char*)key.data();

       /* ofstream outfile;
        outfile.open("D:\log.txt", ios::app);
        outfile <<res<< "key:" << key << endl;*/
        return key;
    }
}

extern "C"
{
    /*************************************************************************
    ** Example of init function
    ** Arguments:
    ** initid	Points to a structure that the init function should fill.
    **		This argument is given to all other functions.
    **	bool maybe_null	1 if function can return NULL
    **				Default value is 1 if any of the arguments
    **				is declared maybe_null.
    **	unsigned int decimals	Number of decimals.
    **				Default value is max decimals in any of the
    **				arguments.
    **	unsigned int max_length  Length of string result.
    **				The default value for integer functions is 21
    **				The default value for real functions is 13+
    **				default number of decimals.
    **				The default value for string functions is
    **				the longest string argument.
    **	char *ptr;		A pointer that the function can use.
    **
    ** args		Points to a structure which contains:
    **	unsigned int arg_count		Number of arguments
    **	enum Item_result *arg_type	Types for each argument.
    **					Types are STRING_RESULT, REAL_RESULT
    **					and INT_RESULT.
    **	char **args			Pointer to constant arguments.
    **					Contains 0 for not constant argument.
    **	unsigned long *lengths;		max string length for each argument
    **	char *maybe_null		Information of which arguments
    **					may be NULL
    **
    ** message	Error message that should be passed to the user on fail.
    **		The message buffer is MYSQL_ERRMSG_SIZE big, but one should
    **		try to keep the error message less than 80 bytes long!
    **
    ** This function should return 1 if something goes wrong. In this case
    ** message should contain something usefull!
    **************************************************************************/
    bool encrypt_init(UDF_INIT* initid, UDF_ARGS* args, char* message) {
        if (args->arg_count != 1) {
            strcpy_s(message,63, "wrong number of arguments: int_encrypt() requires one argument");
            return true;
        }

        initid->max_length = args->lengths[0];
        initid->maybe_null = true;
        initid->const_item = true;
        return false;
    }
    /****************************************************************************
    ** Deinit function. This should free all resources allocated by
    ** this function.
    ** Arguments:
    ** initid	Return value from xxxx_init
    ****************************************************************************/
     void encrypt_deinit(UDF_INIT* initid){}
    /***************************************************************************
    ** UDF long long function.
    ** Arguments:
    ** initid	Return value from xxxx_init
    ** args		The same structure as to xxx_init. This structure
    **		contains values for all parameters.
    **		Note that the functions MUST check and convert all
    **		to the type it wants!  Null values are represented by
    **		a NULL pointer
    ** is_null	If the result is null, one should store 1 here.
    ** error	If something goes fatally wrong one should store 1 here.
    **
    ** This function should return the result as a long long
    ***************************************************************************/
     char* encrypt(UDF_INIT* initid, UDF_ARGS* args, char* result, unsigned long *length) {
         string u_key = get_key();
         unsigned char key[17] ;
         unsigned char temp[32];
         memcpy(temp, (unsigned char*)u_key.data(), 32);
         hex2byte(key, temp);
         (*length)--;
         if (*length > args->lengths[0])
             *length = args->lengths[0];
         memcpy(result, args->args[0], *length);
         result[*length] = 0;
         if(u_key=="NULL"){
             return result;
         }
         else{
             /*ofstream outfile;
             outfile.open("D:\\log.txt", ios::app);*/
             unsigned char *input = static_cast<unsigned char*>(malloc(sizeof(unsigned char)* (*length)));
             memcpy(input, (unsigned char*)result, *length);
             input[*length] = 0;
             int len = (int)(*length);
             if (len % 16 != 0)
                 len = (len / 16 + 1) * 16;
             unsigned char *output = static_cast<unsigned char*>(malloc(sizeof(unsigned char) * len));
             //outfile << "encrypt::\n" << "temp:" << temp << ", key:" << key << endl << "input:" << input << ",inlen:" << len;

             sm4_context ctx;
             sm4_setkey_enc(&ctx, key);
             /*outfile << ",in_hex:";
             for (int i = 0; i < len; i++)
                 outfile << hex << (unsigned int)input[i]<<" ";
             outfile << endl;*/
             sm4_crypt_cbc(&ctx, 1, *length, input, output);
             /*outfile << "out_hex:";
             for (int i = 0; i < len; i++)
                 outfile << hex << (unsigned int)output[i]<<" ";*/

             *length = (unsigned long)len;
             output[*length] = 0;
             //outfile <<",outlen:"<<(*length)<< ", output:" << output << endl << endl;
             memcpy(result, (char*)output, *length);
             result[*length] = 0;
             return result;
         }    
    }
}

extern "C"
{
    /*************************************************************************
    ** Example of init function
    ** Arguments:
    ** initid	Points to a structure that the init function should fill.
    **		This argument is given to all other functions.
    **	bool maybe_null	1 if function can return NULL
    **				Default value is 1 if any of the arguments
    **				is declared maybe_null.
    **	unsigned int decimals	Number of decimals.
    **				Default value is max decimals in any of the
    **				arguments.
    **	unsigned int max_length  Length of string result.
    **				The default value for integer functions is 21
    **				The default value for real functions is 13+
    **				default number of decimals.
    **				The default value for string functions is
    **				the longest string argument.
    **	char *ptr;		A pointer that the function can use.
    **
    ** args		Points to a structure which contains:
    **	unsigned int arg_count		Number of arguments
    **	enum Item_result *arg_type	Types for each argument.
    **					Types are STRING_RESULT, REAL_RESULT
    **					and INT_RESULT.
    **	char **args			Pointer to constant arguments.
    **					Contains 0 for not constant argument.
    **	unsigned long *lengths;		max string length for each argument
    **	char *maybe_null		Information of which arguments
    **					may be NULL
    **
    ** message	Error message that should be passed to the user on fail.
    **		The message buffer is MYSQL_ERRMSG_SIZE big, but one should
    **		try to keep the error message less than 80 bytes long!
    **
    ** This function should return 1 if something goes wrong. In this case
    ** message should contain something usefull!
    **************************************************************************/
    bool decrypt_init(UDF_INIT* initid, UDF_ARGS* args, char* message) {
        if (args->arg_count != 1) {
            strcpy_s(message, 63, "wrong number of arguments: int_encrypt() requires one argument");
            return true;
        }
        initid->max_length = args->lengths[0];
        initid->maybe_null = true;
        initid->const_item = true;
        return false;
    }
    /****************************************************************************
    ** Deinit function. This should free all resources allocated by
    ** this function.
    ** Arguments:
    ** initid	Return value from xxxx_init
    ****************************************************************************/
    void decrypt_deinit(UDF_INIT* initid) {}
    /***************************************************************************
    ** UDF long long function.
    ** Arguments:
    ** initid	Return value from xxxx_init
    ** args		The same structure as to xxx_init. This structure
    **		contains values for all parameters.
    **		Note that the functions MUST check and convert all
    **		to the type it wants!  Null values are represented by
    **		a NULL pointer
    ** is_null	If the result is null, one should store 1 here.
    ** error	If something goes fatally wrong one should store 1 here.
    **
    ** This function should return the result as a long long
    ***************************************************************************/
    char* decrypt(UDF_INIT* initid, UDF_ARGS* args, char* result, unsigned long* length) {
        string u_key = get_key();
        unsigned char key[17];
        unsigned char temp[32];
        memcpy(temp, (unsigned char*)u_key.data(), 32);
        hex2byte(key, temp);
        (*length)--;
        if (*length > args->lengths[0])
            *length = args->lengths[0];
        memcpy(result, args->args[0], *length);
        result[*length] = 0;
        if (u_key == "NULL") {
            return result;
        }
        else {
            /*ofstream outfile;
            outfile.open("D:\\log.txt", ios::app);*/
            unsigned char* input = static_cast<unsigned char*>(malloc(sizeof(unsigned char) * (*length)));
            memcpy(input, (unsigned char*)result, *length);
            input[*length] = 0;
            int len = (int)(*length);
            if (len % 16 != 0)
                len = (len / 16 + 1) * 16;
            unsigned char* output = static_cast<unsigned char*>(malloc(sizeof(unsigned char) * len));
            //outfile << "decrypt::\n" << "temp:" << temp << ", key:" << key << endl << "input:" << input << ",inlen:" << len;
             
            sm4_context ctx;
            sm4_setkey_dec(&ctx, key);
            /*outfile << ",in_hex:";
            for (int i = 0; i < len; i++)
                outfile << hex << (unsigned int)input[i];
            outfile << endl;*/
            sm4_crypt_cbc(&ctx, 0, len, input, output);

            int end = (int)output[len - 1];
            if(end<16)
                if (output[len - 1] == output[len - end]) {
                    int flag = 1;
                    for (int i = 1; i <= end; i++) {
                        if ((int)output[len - i] != end) {
                            flag = 0;
                            break;
                        }
                    }
                    if (flag)
                        len -= end;
                }

            /*outfile << "out_hex:";
            for (int i = 0; i < len; i++)
                outfile << hex << (unsigned int)output[i];*/

            *length = (unsigned long)len;
            output[*length] = 0;
            //outfile << ",outlen:" << (*length) << ", output:" << output << endl << endl;
            memcpy(result, (char*)output, *length);
            result[*length] = 0;
            return result;
        }
    }
}

/***************************************************************************
** UDF string function.
** Arguments:
** initid	Structure filled by xxx_init
** args		The same structure as to xxx_init. This structure
**		contains values for all parameters.
**		Note that the functions MUST check and convert all
**		to the type it wants!  Null values are represented by
**		a NULL pointer
** result	Possible buffer to save result. At least 255 byte long.
** length	Pointer to length of the above buffer.	In this the function
**		should save the result length
** is_null	If the result is null, one should store 1 here.
** error	If something goes fatally wrong one should store 1 here.
**
** This function should return a pointer to the result string.
** Normally this is 'result' but may also be an alloced string.
***************************************************************************/


/***************************************************************************
** UDF double function.
** Arguments:
** initid	Structure filled by xxx_init
** args		The same structure as to xxx_init. This structure
**		contains values for all parameters.
**		Note that the functions MUST check and convert all
**		to the type it wants!  Null values are represented by
**		a NULL pointer
** is_null	If the result is null, one should store 1 here.
** error	If something goes fatally wrong one should store 1 here.
**
** This function should return the result.
***************************************************************************/
