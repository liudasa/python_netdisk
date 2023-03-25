import struct, os, threading,hashlib
from socket import *


class Client:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.client: socket = None
        self.client_init()
    def client_init(self):
        while True:
            init()
            self.tcp_init()
            global user_name, password
            # flag为1，说明要注册
            if flag=='1':
                self.send_train('000',self.client)
                self.send_train(user_name, self.client)
                self.send_train(password, self.client)
                data=self.recv_train(self.client).decode('utf8')
                print(data)
                if data=='用户名已存在':
                    self.client.close()
                    continue
                else:
                    user_name = input('请输入用户名（大于四位）：')
                    password = input('请输入密码：')
                    self.client.close()
                    # print('关闭套接字')
                    self.tcp_init()
                    # print('启动tcp')
            # 发送用户名
            self.send_train(user_name.encode('utf8'), self.client)
            # print('发送用户名')
            # 发送密码
            self.send_train(password.encode('utf8'), self.client)
            # print('发送密码')
            # 密码是否正确的信息
            data=self.recv_train(self.client).decode('utf8')
            print(data)
            if data=='登陆成功':
                self.token = self.recv_train(self.client).decode('utf8')
                # print('收到token')
                self.command_send()
                break
            else:
                continue
    def tcp_init(self):
        self.client = socket(AF_INET, SOCK_STREAM)
        self.client.connect((self.ip, self.port))

    def send_train(self, data, client):
        """
        为防止数据粘包设计的协议
        输入待发送数据，以字节流的形式发送数据长度+数据内容
        :param bytes:
        :return:
        """

        if not isinstance(data, bytes):
            data = data.encode('utf8')
        train_head = struct.pack('I', len(data))
        client.send(train_head + data)

    def recv_train(self, client):
        content_len = struct.unpack('I', client.recv(4))[0]
        return client.recv(content_len)

    def command_send(self):
        while True:
            command = input()
            if command[:2] == 'ls':
                self.do_ls()
            elif command[:2] == 'cd':
                self.do_cd(command)
            elif command[:3] == 'pwd':
                self.do_pwd()
            elif command[:5]=='rmall':
                self.do_rmall(command)
            elif command[:5]=='tree':
                self.do_tree(command)
            elif command[:5] == 'rmdir':
                self.do_rmdir(command)
            elif command[:2] == 'rm':
                self.do_rm(command)
            elif command[:5] == 'mkdir':
                self.do_mkdir(command)
            elif command[:4] == 'gets':
                client = socket(AF_INET, SOCK_STREAM)
                client.connect((self.ip, self.port))
                self.send_train(self.token, client)
                self.send_train(command, client)
                t_gets = threading.Thread(target=self.do_gets, args=(command, client))
                t_gets.start()
            elif command[:4] == 'puts':
                file_name = command.split()[1]
                if file_name in os.listdir():
                    client = socket(AF_INET, SOCK_STREAM)
                    client.connect((self.ip, self.port))
                    self.send_train(self.token, client)
                    self.send_train(command, client)
                    t_puts = threading.Thread(target=self.do_puts, args=(file_name, client))
                    t_puts.start()
                else:
                    print('文件不存在')
            else:
                print('wrong command')
    def do_tree(self,command):
        self.send_train(command,self.client)
        print(self.recv_train(self.client).decode('utf8'))
    def do_rmall(self,command):
        self.send_train(command,self.client)

    def do_mkdir(self,command):
        self.send_train(command,self.client)
        print(self.recv_train(self.client).decode('utf8'))
    def do_rmdir(self,command):
        self.send_train(command,self.client)
        print(self.recv_train(self.client).decode('utf8'))
    def do_pwd(self):
        self.send_train('pwd', self.client)
        print(self.recv_train(self.client).decode('utf8'))

    def do_cd(self, command):
        self.send_train(command, self.client)
        print(self.recv_train(self.client).decode('utf8'))

    def do_ls(self):
        self.send_train('ls', self.client)
        print(self.recv_train(self.client).decode('utf8'), end='')

    def do_rm(self, command):
        self.send_train(command, self.client)
        print(self.recv_train(self.client).decode('utf8'))

    def do_puts(self, file_name, client):
        # 发送md5值
        md5_num=md5(file_name)
        # print(md5_num)
        self.send_train(md5_num,client)
        # print('发送md5值')
        flag1 = struct.unpack('I', client.recv(4))[0]
        if flag1:
            flag2 = struct.unpack('I', client.recv(4))[0]
            # print('收到flag：%d'%flag2)
            if flag2:
                file_size = os.stat(file_name).st_size
                client.send(struct.pack('I', file_size))
                # 循环发送文件内容
                total = 0
                f = open(file_name, 'rb')
                while True:
                    file_content = f.read(10000)
                    if file_content:
                        client.send(file_content)
                        total += len(file_content)
                    else:
                        f.close()
                        break
            print('上传完毕')
            client.close()
        else:
            print('该目录下已经存在名为：%s的文件'%file_name)
    def do_gets(self, command, client):
        # 接收一个标记位，判断服务器是否存在该文件
        flag = struct.unpack('I', client.recv(4))[0]
        if flag:
            print('开始接收')
            file_name = command.split()[1]
            # 接收文件大小
            file_size_bytes = client.recv(4)
            file_size = struct.unpack('I', file_size_bytes)[0]
            f = open(file_name, 'wb')
            # 循环接收文件内容
            total = 0
            while True:
                file_content = client.recv(10000)
                f.write(file_content)
                total += len(file_content)
                # 文件接收完毕跳出循环
                if total == file_size:
                    f.close()
                    print('接收完毕')
                    break
        else:
            print('文件不存在')
        client.close()
# md5算法
def md5(file_name):
    f = open(file_name,'rb')
    f_md5 = hashlib.md5()
    f_md5.update(f.read())
    f.close()
    return (f_md5.hexdigest())
def init():
    global user_name, password, flag
    flag = input('登陆请按 0 注册请按 1')
    while True:
        user_name=input('请输入用户名（大于四位）：')
        if len(user_name)<4:
            continue
        password=input('请输入密码：')
        break
if __name__ == '__main__':
    cilent = Client('192.168.74.128', 2000)


