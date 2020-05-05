import sys
import pymysql
from UI_Middleware import Ui_MainWindow
from database_login import Ui_Login_Form
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

db = cursor = cur_tb = None
username = hostname = password = None


class MyMainForm(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MyMainForm, self).__init__(parent)
        self.login = LoginForm()  # 登陆界面类实例化
        self.setupUi(self)
        self.login_pushButton.clicked.connect(self.openForm)
        self.statusbar.showMessage(' MySQL未连接')  # 主界面底部状态栏
        self.db_comboBox.currentIndexChanged.connect(self.db_change)
        self.tb_comboBox.currentIndexChanged.connect(self.tb_change)
        self.move2left_pushButton.clicked.connect(self.move2left)
        self.move2right_pushButton.clicked.connect(self.move2right)

    def openForm(self):  # 点登陆按钮 打开登录框
        global cursor
        self.login.show()
        db_status = self.login.exec_()  # 接收数据库登录框返回的登陆是否成功信息
        # 成功登陆则修改状态栏信息，并将主机中的所有数据库名称添加到数据库下拉菜单中
        if db_status:
            self.statusbar.showMessage(' MySQL已连接')
            cursor = db.cursor()
            cursor.execute('show databases')
            item = []
            for i in cursor.fetchall():
                item.append(i[0])
            self.db_comboBox.clear()
            self.db_comboBox.addItems(item)

            for inx, val in enumerate(item):
                self.db_comboBox.setItemData(inx, val, Qt.ToolTipRole)
            self.statusbar.showMessage(' MySQL已连接| 当前数据库: ' + self.db_comboBox.currentText())

    def db_change(self):  # 数据库下拉菜单选项修改时执行此函数
        self.cur_db = self.db_comboBox.currentText()
        if self.cur_db != '':
            self.statusbar.showMessage(' MySQL已连接| 当前数据库: ' + self.cur_db)
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
            if cur_tb=='':
                self.left_tableWidget.setRowCount(0)
                self.right_tableWidget.setRowCount(0)
            for inx, val in enumerate(item):
                self.tb_comboBox.setItemData(inx, val, Qt.ToolTipRole)

    def tb_change(self):  # 数据表下拉菜单选项修改时执行此函数
        global db, cursor, cur_tb, pk_index, pk_name, v_dict
        cur_tb = self.tb_comboBox.currentText()
        if cur_tb != '':
            self.statusbar.showMessage(' MySQL已连接| 当前数据库: ' + self.cur_db + ', 当前数据表: ' + cur_tb)
            self.tb_comboBox.setToolTip(cur_tb)
            # 下面是读取数据表中的所有属性并根据注释内容是否为加密列添加到对应的列表中
            sql = 'show full columns from ' + cur_tb  # 查询当前表下的所有属性
            cursor.execute(sql)
            res = cursor.fetchall()  # 获取查询结果
            db.commit()
            # 清除列表中现有的数据
            self.left_tableWidget.setRowCount(0)
            self.right_tableWidget.setRowCount(0)
            # 暂时禁用排序，防止向列表中添加时出错
            self.disableSort()
            left_row = right_row = 0
            for val in res:
                # 若注释为空，则添加到左边列表中
                if val[8] == '':
                    left_row += 1
                    self.left_tableWidget.setRowCount(left_row)
                    self.left_tableWidget.setItem(left_row - 1, 0, QTableWidgetItem(val[0]))
                    self.left_tableWidget.setItem(left_row - 1, 1, QTableWidgetItem(val[1]))
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
                    else:
                        left_row += 1
                        self.left_tableWidget.setRowCount(left_row)
                        self.left_tableWidget.setItem(left_row - 1, 0, QTableWidgetItem(val[0]))
                        self.left_tableWidget.setItem(left_row - 1, 1, QTableWidgetItem(val[1]))
            self.enableSort()

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
