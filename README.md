# DatabaseMiddleware
### MySQL数据库加解密插件安装

加解密项目源码在`EncryptionPlugin`文件夹中（也可以直接使用git仓库中的dll文件）

1.使用Visual Studio打开sln项目文件，对项目进行编译生成，默认在`x64\Debug`文件夹下会生成myudf.dll文件。

2.将生成的DLL文件拷贝到MySQL安装目录下的 `lib\plugin`文件夹中（我的是`C:\Program Files\MySQL\MySQL Server 8.0\lib`）

3.执行数据库语句创建加密函数和解密函数

```mysql
CREATE FUNCTION encrypt RETURNS STRING SONAME "myudf.dll";
CREATE FUNCTION decrypt RETURNS STRING SONAME "myudf.dll";
```
⚠⚠⚠加解密的实现需要电脑插入U盘，并且U盘根目录中存在key.key密钥文件
