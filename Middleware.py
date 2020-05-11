import sys
import pymysql
import os
from time import sleep
from psutil import disk_partitions
from UI_Middleware import Ui_MainWindow
from database_login import Ui_Login_Form
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

db = cursor = cur_tb = db_status = None
username = hostname = password = None
ukey_status = 0
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
                    QMessageBox.critical(self,"ERROR",str(e))
                else:
                    db.commit()
                # print("加解密函数\n", sql)
                left_rows = self.left_tableWidget.rowCount()
                right_rows = self.right_tableWidget.rowCount()
                # 读取表格上的数据，执行加解密操作
                # 对新添加到左边表格的数据进行解密
                for i in range(left_rows):
                    name_ = self.left_tableWidget.item(i, 0).text()
                    type_ = self.left_tableWidget.item(i, 1).text()
                    if name_ not in no_encrypted:
                        name_new = name_ + "_NEW"
                        sql1 = "ALTER TABLE " + cur_tb + " ADD COLUMN " + name_new + " " + type_ + " AFTER " + name_ + ";\n"
                        sql2 = "UPDATE " + cur_tb + " SET " + name_new + "=decrypt(CONVERT(" + name_ + ",CHAR));\n"
                        sql3 = "ALTER TABLE " + cur_tb + " DROP COLUMN " + name_ + ";\n"
                        sql4 = "ALTER TABLE " + cur_tb + " CHANGE COLUMN " + name_new + " " + name_ + " " + type_ + ";\n"
                        # print("解密\n", sql)
                        try:
                            cursor.execute(sql1)
                            cursor.execute(sql2)
                            cursor.execute(sql3)
                            cursor.execute(sql4)
                        except Exception as e:
                            db.rollback()
                            QMessageBox.critical(self, "ERROR", str(e))
                        else:
                            db.commit()
                # 对新添加到右边表格的数据进行加密并添加触发器
                encrypt_list = []
                sql1 = "DROP TRIGGER IF EXISTS insert_data;"
                sql2 = "DROP TRIGGER IF EXISTS update_data;"
                try:
                    cursor.execute(sql1)
                    cursor.execute(sql2)
                except Exception as e:
                    db.rollback()
                    QMessageBox.critical(self, "ERROR", str(e))
                else:
                    db.commit()
                insert_trigger = "CREATE TRIGGER insert_data\n"
                insert_trigger += "BEFORE INSERT ON " + cur_tb + " FOR EACH ROW BEGIN\n"
                update_trigger = "CREATE TRIGGER update_data\n"
                update_trigger += "BEFORE UPDATE ON " + cur_tb + " FOR EACH ROW BEGIN\n"
                for i in range(right_rows):
                    name_ = self.right_tableWidget.item(i, 0).text()
                    type_ = self.right_tableWidget.item(i, 1).text()
                    encrypt_list.append(name_)
                    if name_ not in encrypted:
                        # encrypt this attr
                        name_old = name_ + "_OLD"
                        sql1 = "ALTER TABLE " + cur_tb + " CHANGE COLUMN " + name_ +" "+name_old +" "+type_ + ";"
                        sql2 = "ALTER TABLE " + cur_tb + " ADD COLUMN " + name_ + " TEXT CHARACTER SET ascii COLLATE ascii_general_ci AFTER " + name_old + ";"
                        sql3 = "ALTER TABLE " + cur_tb + " MODIFY COLUMN " + name_ + " TEXT CHARACTER SET ascii COLLATE ascii_general_ci COMMENT 'en," + type_ + "';"
                        sql4 = "UPDATE " + cur_tb + " SET " + name_ + "=encrypt(CONVERT(" + name_old + ",CHAR));"
                        sql5 = "ALTER TABLE " + cur_tb + " DROP COLUMN " + name_old + ";"
                        # print("加密\n", sql)
                        try:
                            cursor.execute(sql1)
                            cursor.execute(sql2)
                            cursor.execute(sql3)
                            cursor.execute(sql4)
                            cursor.execute(sql5)
                        except Exception as e:
                            db.rollback()
                            QMessageBox.critical(self, "ERROR", str(e))
                        else:
                            db.commit()
                    # 添加触发器语句
                    insert_trigger += "SET NEW." + name_ + "=encrypt(CONVERT(NEW." + name_ + ",CHAR));\n"
                    update_trigger += "IF (OLD." + name_ + " != NEW." + name_ + ") THEN\n"
                    update_trigger += "SET NEW." + name_ + "=encrypt(CONVERT(NEW." + name_ + ",CHAR));\nEND IF;\n"
                insert_trigger += "END"
                update_trigger += "END"
                # print("触发器\n", sql)
                try:
                    cursor.execute(insert_trigger)
                    cursor.execute(update_trigger)
                except Exception as e:
                    db.rollback()
                    QMessageBox.critical(self, "ERROR", str(e))
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
                        sql2 += "CONVERT(decrypt(CONVERT(" + val + ",CHAR)) USING utf8) " + val
                    else:
                        sql2 += val
                sql2 += " FROM " + cur_tb + ";"
                # print("视图\n", sql)
                try:
                    cursor.execute(sql1)
                    cursor.execute(sql2)
                except Exception as e:
                    db.rollback()
                    QMessageBox.critical(self, "ERROR", str(e))
                else:
                    db.commit()
            self.refresh_table()

    def detect_ukey(self):
        self.detect = existUkey()
        self.detect.exist_signal.connect(self.updataStatusbar)
        self.detect.start()

    def updataStatusbar(self, status):
        if status:
            self.statusbar.showMessage(' MySQL已连接| UKey已插入')
        else:
            self.statusbar.showMessage(' MySQL已连接| 未检测到UKey')


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
