# DatabaseMiddleware
## 使用说明

开发环境：Visual Studio 2019、Python 3.7、MySQL 8.0.19

下载[发布版本](https://github.com/BayMRX/DatabaseMiddleware/releases)压缩包，解压后直接运行即可。

⚠注：首次运行需要使用管理员权限打开程序，程序会自动将加解密插件安装到MySQL中，否则程序将无法运行！
------如果程序运行报错，请尝试使用源码重新编译dll插件

## 源码编译
### MySQL数据库加解密插件手动安装

加解密插件的源码在`EncryptionPlugin`文件夹中

在此目录中进行以下操作：

1.修改`CMakeList.txt`文件中MySQL库的路径
```
INCLUDE_DIRECTORIES("C:\Program Files\MySQL\MySQL Server 8.0\include")
```

2.使用**CMake**创建Visual Studio项目和解决方案文件，'generator'值需要自行替换（如果有必要，需要先从[CMake官网](http://www.cmake.org)获取相关程序安装）

```powershell
cmake -G "generator"
```
使用**cmake --help**会显示出所有可用的生成器列表

3.使用Visual Studio打开CMake生成的`.sln`项目文件，然后重新生成项目，编译完成后会在项目根目录的`Debug`文件夹中生成`
myudf.dll`文件，然后将此dll文件拷贝到到MySQL安装目录下的`lib\plugin`文件夹中（我的是`C:\Program Files\MySQL\MySQL Server 8.0\lib`）
，或者拷贝到exe程序的同一目录下

4.(可选)手动执行SQL语句创建加密函数和解密函数
```mysql
CREATE FUNCTION encrypt RETURNS STRING SONAME "myudf.dll";
CREATE FUNCTION decrypt RETURNS STRING SONAME "myudf.dll";
```
⚠⚠⚠加解密的实现需要电脑插入U盘，并且U盘根目录中存在key.key密钥文件
