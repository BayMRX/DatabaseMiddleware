PROJECT(myudf)

# Path for MySQL include directory
INCLUDE_DIRECTORIES("C:\Program Files\MySQL\MySQL Server 8.0\include")

ADD_DEFINITIONS("-DHAVE_DLOPEN")
ADD_LIBRARY(myudf MODULE myudf.cpp myudf.def)
TARGET_LINK_LIBRARIES(myudf wsock32)