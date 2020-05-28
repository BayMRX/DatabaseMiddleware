import sys
import pymysql
import os
from time import sleep, time
from psutil import disk_partitions
from UI_Middleware import Ui_MainWindow
from database_login import Ui_Login_Form
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

db = cursor = cur_tb = db_status = None
username = hostname = password = None
ukey_status = 0
fin_flag = 0
encrypted = []
no_encrypted = []
attr_list = []


class MyMainForm(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MyMainForm, self).__init__(parent)
        self.login = LoginForm()  # 登陆界面类实例化
        self.setupUi(self)
        self.login_pushButton.clicked.connect(self.openForm)
        self.statusbar.showMessage(' MySQL已连接| 未检测到UKey')  # 主界面底部状态栏
        self.db_comboBox.currentIndexChanged.connect(self.db_change)
        self.tb_comboBox.currentIndexChanged.connect(self.tb_change)
        self.move2left_pushButton.clicked.connect(self.move2left)
        self.move2right_pushButton.clicked.connect(self.move2right)
        self.apply_pushButton.clicked.connect(self.apply)
        self.detect_ukey()

    def openForm(self):  # 点登陆按钮 打开登录框
        global cursor, db_status
        self.login.show()
        db_status = self.login.exec_()  # 接收数据库登录框返回的登陆是否成功信息
        # 成功登陆则修改状态栏信息，并将主机中的所有数据库名称添加到数据库下拉菜单中
        if db_status:
            if ukey_status:
                self.statusbar.showMessage(' MySQL已连接| UKey已插入')
            else:
                self.statusbar.showMessage(' MySQL已连接| 未检测到UKey')
            cursor = db.cursor()
            # 判断加解密插件是否安装，未安装则弹出提示
            cursor.execute("show variables like '%basedir%' ")
            db_path = cursor.fetchone()
            plugin_path = db_path[1] + "lib\\plugin\\"
            if not os.path.exists(plugin_path + "myudf.dll"):
                cmd = "copy .\myudf.dll \"" + plugin_path + "\""
                os.system(cmd)
            if not os.path.exists(plugin_path + "myudf.dll"):
                rec_code = QMessageBox.critical(self, "ERROR!", "当前数据库未安装加解密插件，请重新使用管理员身份打开软件进行安装")
                if rec_code != 65536:
                    sys.exit(app.exec_())
            # 显示数据库信息
            cursor.execute("show databases")
            item = []
            for i in cursor.fetchall():
                item.append(i[0])
            self.db_comboBox.clear()
            self.db_comboBox.addItems(item)
            # 添加提示
            for inx, val in enumerate(item):
                self.db_comboBox.setItemData(inx, val, Qt.ToolTipRole)

    def db_change(self):  # 数据库下拉菜单选项修改时执行此函数
        self.cur_db = self.db_comboBox.currentText()
        if self.cur_db != '':
            self.db_comboBox.setToolTip(self.cur_db)
            # print(type(cur_db),cur_db)
            db.select_db(self.cur_db)
            # 将当前所选数据库中的所有表添加到数据表下拉菜单中
            cursor.execute("show full tables where Table_type = 'BASE TABLE' ")
            item = []
            for i in cursor.fetchall():
                item.append(i[0])
            self.tb_comboBox.clear()
            self.tb_comboBox.addItems(item)
            if cur_tb == '':
                self.left_tableWidget.setRowCount(0)
                self.right_tableWidget.setRowCount(0)
            for inx, val in enumerate(item):
                self.tb_comboBox.setItemData(inx, val, Qt.ToolTipRole)

    def tb_change(self):  # 数据表下拉菜单选项修改时执行此函数
        global cur_tb
        cur_tb = self.tb_comboBox.currentText()
        if cur_tb != '':
            self.tb_comboBox.setToolTip(cur_tb)
            self.refresh_table()

    def refresh_table(self):
        global db, cursor, cur_tb, encrypted, no_encrypted, attr_list
        # 下面是读取数据表中的所有属性并根据注释内容是否为加密列添加到对应的列表中
        sql = 'show full columns from ' + cur_tb  # 查询当前表下的所有属性
        cursor.execute(sql)
        res = cursor.fetchall()  # 获取查询结果
        db.commit()
        # 清除列表中现有的数据
        no_encrypted.clear()
        encrypted.clear()
        attr_list.clear()
        self.left_tableWidget.setRowCount(0)
        self.right_tableWidget.setRowCount(0)
        # 暂时禁用排序，防止向列表中添加时出错
        self.disableSort()
        left_row = right_row = 0
        for val in res:
            attr_list.append(val[0])
            # 若注释为空，则添加到左边列表中
            if val[8] == '':
                left_row += 1
                self.left_tableWidget.setRowCount(left_row)
                self.left_tableWidget.setItem(left_row - 1, 0, QTableWidgetItem(val[0]))
                self.left_tableWidget.setItem(left_row - 1, 1, QTableWidgetItem(val[1]))
                no_encrypted.append(val[0])
                # sql = "ALTER TABLE " + cur_tb + " MODIFY COLUMN " + val[0] + " " + val[1] + " COMMENT '" + val[1] + "'"
                # cursor.execute(sql)
            else:
                # 注释不为空则将注释按逗号分隔成单词列表，若加密列（列表第一个元素标记为en）则添加到右边列表中，否则添加到左边列表中
                comm = val[8].split(",")
                if comm[0] == "en":
                    right_row += 1
                    self.right_tableWidget.setRowCount(right_row)
                    self.right_tableWidget.setItem(right_row - 1, 0, QTableWidgetItem(val[0]))
                    self.right_tableWidget.setItem(right_row - 1, 1, QTableWidgetItem(comm[1]))
                    encrypted.append(val[0])
                else:
                    left_row += 1
                    self.left_tableWidget.setRowCount(left_row)
                    self.left_tableWidget.setItem(left_row - 1, 0, QTableWidgetItem(val[0]))
                    self.left_tableWidget.setItem(left_row - 1, 1, QTableWidgetItem(val[1]))
                    no_encrypted.append(val[0])
        self.enableSort()

    # 禁止排序和启用排序，防止在列表元素变化时出现问题
    def disableSort(self):
        QTableView.setSortingEnabled(self.left_tableWidget, False)
        QTableView.setSortingEnabled(self.right_tableWidget, False)

    def enableSort(self):
        QTableView.setSortingEnabled(self.left_tableWidget, True)
        QTableView.setSortingEnabled(self.right_tableWidget, True)
        QTableWidget.resizeRowsToContents(self.left_tableWidget)
        QTableWidget.resizeRowsToContents(self.right_tableWidget)

    # 右边属性列表中的元素添加到左边
    def move2left(self):
        val = self.right_tableWidget.selectedItems()
        index = self.right_tableWidget.selectedIndexes()
        left_rowCount = self.left_tableWidget.rowCount()
        del_li = []
        self.disableSort()
        for i in range(0, len(val), 2):
            left_rowCount += 1
            self.left_tableWidget.setRowCount(left_rowCount)
            self.left_tableWidget.setItem(left_rowCount - 1, 0, QTableWidgetItem(val[i].text()))
            self.left_tableWidget.setItem(left_rowCount - 1, 1, QTableWidgetItem(val[i + 1].text()))
            del_li.append(index[i].row())
        del_li.sort(reverse=True)
        for i in del_li:
            self.right_tableWidget.removeRow(i)
        self.enableSort()

    # 左边属性列表中的元素添加到右边
    def move2right(self):
        val = self.left_tableWidget.selectedItems()
        index = self.left_tableWidget.selectedIndexes()
        right_rowCount = self.right_tableWidget.rowCount()
        del_li = []
        self.disableSort()
        for i in range(0, len(val), 2):
            right_rowCount += 1
            self.right_tableWidget.setRowCount(right_rowCount)
            self.right_tableWidget.setItem(right_rowCount - 1, 0, QTableWidgetItem(val[i].text()))
            self.right_tableWidget.setItem(right_rowCount - 1, 1, QTableWidgetItem(val[i + 1].text()))
            del_li.append(index[i].row())
        del_li.sort(reverse=True)
        for i in del_li:
            self.left_tableWidget.removeRow(i)
        self.enableSort()

    def apply(self):
        global ukey_status, db, cursor, cur_tb, encrypted, no_encrypted, attr_list
        if db_status:
            if not ukey_status:
                QMessageBox.warning(self, "Warning!", "请先插入UKey！")
            else:
                self.progressBar.setValue(0)
                left_rows = self.left_tableWidget.rowCount()
                right_rows = self.right_tableWidget.rowCount()
                left_items = []
                for i in range(left_rows):
                    name_ = self.left_tableWidget.item(i, 0).text()
                    type_ = self.left_tableWidget.item(i, 1).text()
                    left_items.append([name_, type_])
                right_items = []
                for i in range(right_rows):
                    name_ = self.right_tableWidget.item(i, 0).text()
                    type_ = self.right_tableWidget.item(i, 1).text()
                    right_items.append([name_, type_])
                self.data_op = data_operate(left_items, right_items)
                self.data_op.pb_signal.connect(self.update_pb)
                self.data_op.err_signal.connect(self.err_info)
                self.data_op.fin_signal.connect(self.finishDialog)
                self.data_op.start()

    def detect_ukey(self):
        self.detect = existUkey()
        self.detect.exist_signal.connect(self.updataStatusbar)
        self.detect.start()

    def updataStatusbar(self, status):
        if status:
            self.statusbar.showMessage(' MySQL已连接| UKey已插入')
        else:
            self.statusbar.showMessage(' MySQL已连接| 未检测到UKey')

    def update_pb(self, pb_val):
        self.progressBar.setValue(pb_val*100)
        # print("process:",pb_val)

    def err_info(self, info):
        QMessageBox.critical(self, 'ERROR', info)
        # self.widget.setEnabled(True)

    def finishDialog(self, info):
        QMessageBox.information(self, 'Done', info, QMessageBox.Ok, QMessageBox.Ok)
        self.refresh_table()
        # self.widget.setEnabled(True)  # 水印添加完成后恢复所有组件状态


class data_operate(QThread):
    pb_signal = pyqtSignal(float)
    err_signal = pyqtSignal(str)
    fin_signal = pyqtSignal(str)

    def __init__(self, left_items, right_items):
        super(data_operate, self).__init__()
        self.left_items = left_items
        self.right_items = right_items

    def run(self):
        global cur_tb, cursor, db, encrypted, no_encrypted, attr_list, fin_flag

        # 计算所需要加解密的属性数量和被操作的记录数量，以便对进度条进行估算
        time_start = time()
        op_attrNum = 0
        for val in self.left_items:
            if val[0] not in no_encrypted:
                op_attrNum += 1
        for val in self.right_items:
            if val[0] not in encrypted:
                op_attrNum += 1
        cursor.execute('SELECT * FROM ' + cur_tb)
        SumRowNum = cursor.rowcount
        fin_flag = 0
        self.processBar = pb_calc(time_start, op_attrNum, SumRowNum)
        self.processBar.pb_signal.connect(self.update_pb)
        self.processBar.start()
        # 创建加解密函数
        sql1 = "DROP FUNCTION IF EXISTS encrypt;"
        sql2 = "DROP FUNCTION IF EXISTS decrypt;"
        sql3 = "CREATE FUNCTION encrypt RETURNS STRING SONAME \"myudf.dll\";"
        sql4 = "CREATE FUNCTION decrypt RETURNS STRING SONAME \"myudf.dll\";"
        try:
            cursor.execute(sql1)
            cursor.execute(sql2)
            cursor.execute(sql3)
            cursor.execute(sql4)
        except Exception as e:
            db.rollback()
            self.err_signal.emit("加解密函数创建失败！\n"+str(e))
        else:
            db.commit()
        # print("加解密函数\n", sql)
        # left_rows = self.left_tableWidget.rowCount()
        # right_rows = self.right_tableWidget.rowCount()
        # 读取表格上的数据，执行加解密操作
        # 对新添加到左边表格的数据进行解密
        first_flag = True
        for val in self.left_items:
            name_ = val[0]
            type_ = val[1]
            if name_ not in no_encrypted:
                name_new = name_ + "_NEW"
                if first_flag:
                    first_flag = False
                    sql1 = "ALTER TABLE " + cur_tb + " ADD COLUMN " + name_new + " " + type_ + " AFTER " + name_
                    sql2 = "UPDATE " + cur_tb + " SET " + name_new + "=decrypt(CONVERT(" + name_ + ",CHAR))"
                    sql3 = "ALTER TABLE " + cur_tb + " DROP COLUMN " + name_ + " ,CHANGE COLUMN " + name_new + " " + name_ + " " + type_
                else:
                    sql1 += ",ADD COLUMN " + name_new + " " + type_ + " AFTER " + name_
                    sql2 += "," + name_new + "=decrypt(CONVERT(" + name_ + ",CHAR))"
                    sql3 += ",DROP COLUMN " + name_ + ",CHANGE COLUMN " + name_new + " " + name_ + " " + type_
        sql1 += ";"
        sql2 += ";"
        sql3 += ";"
        # print("解密\n")
        # print(sql1,"\n",sql2,"\n",sql3)
        if not first_flag:
            try:
                cursor.execute(sql1)
                cursor.execute(sql2)
                cursor.execute(sql3)
            except Exception as e:
                db.rollback()
                self.err_signal.emit("解密操作失败！\n"+str(e))
            else:
                db.commit()
        # 对新添加到右边表格的数据进行加密并添加触发器
        encrypt_list = []
        sql1 = "DROP TRIGGER IF EXISTS insert_data;\n"
        sql2 = "DROP TRIGGER IF EXISTS update_data;\n"
        # print("删除触发器\n")
        # print(sql)
        try:
            cursor.execute(sql1)
            cursor.execute(sql2)
        except Exception as e:
            db.rollback()
            self.err_signal.emit(str(e))
        else:
            db.commit()
        insert_trigger = "CREATE TRIGGER insert_data\n"
        insert_trigger += "BEFORE INSERT ON " + cur_tb + " FOR EACH ROW BEGIN\n"
        update_trigger = "CREATE TRIGGER update_data\n"
        update_trigger += "BEFORE UPDATE ON " + cur_tb + " FOR EACH ROW BEGIN\n"
        first_flag = True
        for val in self.right_items:
            name_ = val[0]
            type_ = val[1]
            encrypt_list.append(name_)
            if name_ not in encrypted:
                # encrypt this attr
                name_old = name_ + "_OLD"
                if first_flag:
                    first_flag = False
                    sql1 = "ALTER TABLE " + cur_tb + " CHANGE COLUMN " + name_ + " " + name_old + " " + type_ + ",ADD COLUMN " + name_ + " TEXT CHARACTER SET ascii COLLATE ascii_general_ci AFTER " + name_old
                    sql2 = "ALTER TABLE " + cur_tb + " MODIFY COLUMN " + name_ + " TEXT CHARACTER SET ascii COLLATE ascii_general_ci COMMENT 'en," + type_ + "'"
                    sql3 = "UPDATE " + cur_tb + " SET " + name_ + "=encrypt(CONVERT(" + name_old + ",CHAR))"
                    sql4 = "ALTER TABLE " + cur_tb + " DROP COLUMN " + name_old
                else:
                    sql1 += ",CHANGE COLUMN " + name_ + " " + name_old + " " + type_ + ",ADD COLUMN " + name_ + " TEXT CHARACTER SET ascii COLLATE ascii_general_ci AFTER " + name_old
                    sql2 += ",MODIFY COLUMN " + name_ + " TEXT CHARACTER SET ascii COLLATE ascii_general_ci COMMENT 'en," + type_ + "'"
                    sql3 += "," + name_ + "=encrypt(CONVERT(" + name_old + ",CHAR))"
                    sql4 += ",DROP COLUMN " + name_old

            # self.pb_signal.emit(0.99)
            # 添加触发器语句
            insert_trigger += "SET NEW." + name_ + "=encrypt(CONVERT(NEW." + name_ + ",CHAR));\n"
            update_trigger += "IF (OLD." + name_ + " != NEW." + name_ + ") THEN\n"
            update_trigger += "SET NEW." + name_ + "=encrypt(CONVERT(NEW." + name_ + ",CHAR));\nEND IF;\n"
        insert_trigger += "END"
        update_trigger += "END"
        # print("加密\n")
        sql1 += ";"
        sql2 += ";"
        sql3 += ";"
        sql4 += ";"
        # print("触发器\n")
        if not first_flag:
            try:
                cursor.execute(sql1)
                cursor.execute(sql2)
                cursor.execute(sql3)
                cursor.execute(sql4)
            except Exception as e:
                db.rollback()
                self.err_signal.emit("加密操作失败！\n"+str(e))
            else:
                db.commit()
        # print("创建触发器")
        try:
            cursor.execute(insert_trigger)
            cursor.execute(update_trigger)
        except Exception as e:
            db.rollback()
            self.err_signal.emit("触发器创建失败！"+str(e))
        else:
            db.commit()
        # 创建视图
        sql1 = "DROP VIEW IF EXISTS `" + cur_tb + "_view`;"
        sql2 = "CREATE VIEW " + cur_tb + "_view AS\n SELECT "
        flag = 0
        for val in attr_list:
            if flag:
                sql2 += ","
            flag = 1
            if val in encrypt_list:
                sql2 += "CONVERT(decrypt(CONVERT(" + val + ",CHAR)) USING ascii) " + val
            else:
                sql2 += val
        sql2 += " FROM " + cur_tb + ";"
        # print("视图\n")
        try:
            cursor.execute(sql1)
            cursor.execute(sql2)
        except Exception as e:
            db.rollback()
            self.err_signal.emit("视图创建失败！"+str(e))
        else:
            db.commit()
        time_end = time()
        # print("time:", time_end - time_start)
        # print(op_attrNum, SumRowNum)
        fin_flag = 1
        self.pb_signal.emit(1)
        use_time = time_end-time_start
        # log = open("D:/log.txt","a")
        # log.write("%.4f," % use_time)
        # log.close()
        self.fin_signal.emit("操作完成!  \n用时：%.4fs" % use_time)

    def update_pb(self,pb_val):
        self.pb_signal.emit(pb_val)

class pb_calc(QThread):
    pb_signal = pyqtSignal(float)

    def __init__(self,time_start,op_attrNum,SumRowNum):
        super(pb_calc,self).__init__()
        self.time_start = time_start
        self.op_attrNum = op_attrNum
        self.SumRowNum = SumRowNum

    def run(self):
        global fin_flag
        guess_time = 0.00033*self.SumRowNum*self.op_attrNum+1.0536
        percent = (time() - self.time_start) / guess_time
        percent_old = percent
        # str1 = str(percent)
        while percent < 1.00:
            percent = (time()-self.time_start)/guess_time
            # str1 += ","+str(percent)
            if percent-percent_old > 0.01 and not fin_flag:
                percent_old = percent
                self.pb_signal.emit(percent)
                # print("fun:",percent)
            sleep(0.01)
        # print(str1)


class existUkey(QThread):
    exist_signal = pyqtSignal(int)

    def __init__(self):
        super(existUkey, self).__init__()

    def run(self):
        global ukey_status
        while True:
            # 设置Ukey存在标志
            flag = 0
            #  检测所有的驱动器，进行遍历寻找哦
            for item in disk_partitions():
                if 'removable' in item.opts:
                    driver, opts = item.device, item.opts
                    #  判断可移动驱动器内是否存在密钥文件，即是否有Ukey插入
                    if os.path.exists(driver + 'key.key'):
                        flag = 1
                        break
            if flag != ukey_status:
                ukey_status = flag
                self.exist_signal.emit(ukey_status)
            #  设置轮询时间
            sleep(1)


# 数据库登录窗口类
class LoginForm(QDialog, Ui_Login_Form):
    def __init__(self, parent=None):
        super(LoginForm, self).__init__(parent)
        self.setupUi(self)
        self.login_pushButton.clicked.connect(self.login)  # 槽函数，点击按钮后登陆

    def login(self):
        global db, username, hostname, password
        username = self.user_lineEdit.text()
        if not username:  # 不输入username则默认以root登陆
            self.user_lineEdit.setText('root')
            username = 'root'
        hostname = self.host_lineEdit.text()
        if not hostname:  # 不输入hostname则默认连接localhost登陆
            self.host_lineEdit.setText('localhost')
            hostname = 'localhost'
        password = self.pwd_lineEdit.text()
        # 使用pymysql模块进行数据库的连接
        try:
            db = pymysql.connect(hostname, username, password)
            QMessageBox.information(self, 'Database connection', 'Database connection success.')  # 弹出数据库连接成功提示框
            self.accept()  # 关闭登陆，并给主窗口返回True
        except pymysql.Error as e:
            QMessageBox.critical(self, 'Database Connection', e.args[1])  # 弹出数据库连接错误提示


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MyMainForm()
    main.show()  # 启动主界面
    sys.exit(app.exec_())
