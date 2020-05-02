from random import *
import string

key = "".join([choice("abcdef" + string.digits) for i in range(32)])
print(key)
key_file = open('./key.key', 'w')
key_file.writelines(key)
key_file.close()
