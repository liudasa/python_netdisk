from socket import *
import struct,os,select,random,string,shutil,hashlib
from multiprocessing import Manager, Pool
from pymysql import *
file_tree=''
class Server:
    def __init__(self, ip, port):
        self.s_listen: socket = None
        self.ip = ip
        self.port = port
        self.tcp_init()
        self.po = Pool(2)
        # 系统路径，在用户眼里是根路径
        self.sever_path=os.getcwd()
        # 用于统一存放文件的路径,系统设置用户名长度大于4,不会发生与用户路径冲突的问题
        self.sever_file_path=self.sever_path+'/ser'
        os.chdir(self.sever_path)
        try:
            os.mkdir('ser')
        except:
            pass
        # epoll监听s_listen
        self.epoll=select.epoll()
        self.epoll.register(self.s_listen.fileno(), select.EPOLLIN)
        # 存放已经连接的用户
        self.user_dist={}
        # 存放token
        self.token={}

    def tcp_init(self):
        self.s_listen = socket(AF_INET, SOCK_STREAM)
        self.s_listen.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.s_listen.bind((self.ip, self.port))
        self.s_listen.listen(128)

    def task(self):
        while True:
            events = self.epoll.poll()
            for fd, event in events:
                # 缺少用户发送错误用户名的功能
                if fd == self.s_listen.fileno():
                    new_client,_=self.s_listen.accept()
                    data=recv_train(new_client).decode('utf8')
                    # 发送过来的是'000'，注册用户
                    if data == '000':
                        print('注册信息')
                        user_name=recv_train(new_client).decode('utf8')
                        password=recv_train(new_client).decode('utf8')
                        # 如果用户名之前存在
                        if conn.select1('user','name',user_name):
                            send_train('用户名已存在',new_client)
                        else:
                            send_train('注册成功',new_client)
                            conn.insert('user',(0,user_name,password))
                            # 为每个新用户新建一个目录
                            os.chdir(self.sever_path)
                            os.mkdir(user_name)
                    # 发的是用户名，监控new_client+发送token
                    elif conn.select1('user','name',data):
                        print('收到用户名')
                        password=recv_train(new_client).decode('utf8')
                        print('收到密码')
                        # 缺少判断用户密码是否正确的功能
                        if conn.select2('user','name','password',data)==password:
                            send_train('登陆成功',new_client)
                            user_name=data
                            self.epoll.register(new_client.fileno(),select.EPOLLIN)
                            print('将new_client放入进程池')
                            user = User()
                            # 用户自己的目录初始为 /
                            user.path='/'
                            user.name=user_name
                            # 用于处理服务器目录与客户端目录长度不一致问题
                            user.hide_len=len(self.sever_path+'/'+user.name)
                            user.new_client=new_client
                            self.user_dist[new_client.fileno()]=user
                            token=get_token()
                            user.send_train(token)
                            # 建立token和user的映射
                            self.token[token]=user
                            user.token=token
                        else:
                            send_train('密码错误',new_client)
                    # 用户发的是token
                    elif data in self.token:
                        # 根据token找到用户
                        user=self.token[data]
                        command=recv_train(new_client).decode('utf8')
                        # 服务器端的工作路径，用户不感知
                        print(self.sever_path)
                        print(user.path)
                        print(user.name)
                        work_path=self.sever_path+'/'+user.name+'/'+user.path
                        print(work_path)
                        if command[:4]=='gets':
                            self.po.apply_async(do_gets,args=(command,new_client,work_path))
                            # new_client.close()
                        elif command[:4]=='puts':
                            self.po.apply_async(do_puts, args=(command, new_client,work_path,self.sever_file_path,user))
                            # new_client.close()
                    # 收到的是用户名，但是数据库中没有
                    else:
                        send_train('不存在此用户',new_client)
                # 如果是客户端响应
                elif event==select.EPOLLIN:
                    # 还缺少客户端开把client从字典中拿出去的功能
                    # 得到用户
                    user=self.user_dist[fd]
                    # 得到指令
                    try:
                        command=user.recv_train().decode('utf8')
                    except struct.error:
                        # 客户端断开
                        self.epoll.unregister(fd)
                        user.new_client.close()
                        del self.user_dist[fd]
                        del self.token[user.token]
                    else:
                        print(self.sever_path)
                        print(user.path)
                        print(user.name)
                        work_path=self.sever_path+'/'+user.name+'/'+user.path
                        print(work_path)
                        user.deal_command(command,work_path,self.sever_file_path)
class User:
    """
    每一个user对象对应一个客户端
    """

    def __init__(self):
        self.new_client: socket =None
        self.path = os.getcwd()
        self.token=None
        self.name=None
        self.hide_len=None
    def deal_command(self,command,*args):
        """
        接收从客户端发出的命令，根据不同的命令执行不同的函数
        :return:
        """
        while True:
            if command[:2] == 'ls':
                self.do_ls(args[0])
                break
            elif command[:2] == 'cd':
                self.do_cd(command,args[0])
                break
            elif command[:3] == 'pwd':
                self.do_pwd()
                break
            elif command[:5] == 'rmdir':
                self.do_rmdir(command,args[0])
                break
            elif command[:5]=='tree':
                self.do_tree(args[0])
                break
            elif command[:5]=='rmall':
                self.do_rmall(command,args[0])
                break
            elif command[:2] == 'rm':
                self.do_rm(command,args[0],args[1])
                break
            elif command[:5] == 'mkdir':
                self.do_mkdir(command,args[0])
                break
    def send_train(self, data):
        """
        为防止数据粘包设计的协议
        输入待发送数据，以字节流的形式发送数据长度+数据内容
        :param bytes:
        :return:
        """
        if not isinstance(data,bytes):
            data=data.encode('utf8')
        train_head = struct.pack('I', len(data))
        self.new_client.send(train_head + data)

    def recv_train(self):
        '''
        为防止数据粘包设计的协议
        根据send_train发送的字节流，解析出数据内容对应的字节流并返回
        :return:
        '''
        try:
            content_len = struct.unpack('I', self.new_client.recv(4))[0]
        except struct.error as e:
            raise e
        else:
            return self.new_client.recv(content_len)
    def do_tree(self,work_path):
        global file_tree
        os.chdir(work_path)
        path=os.getcwd()
        try:
            dfs_dir(path,0)
        except Exception as e:
            self.send_train(str(e))
        else:
            self.send_train(file_tree)
        file_tree=''





    def do_rmall(self,command,work_path):
        try:
            os.chdir(work_path)
            path=os.getcwd()+'/'+command.split()[1]
            del_file(path)
        except:
            pass


    def do_mkdir(self,command,work_path):
        try:
            os.chdir(work_path)
            os.mkdir(command.split()[1])
        except Exception as e:
            self.send_train(str(e))
        else:
            self.send_train('创建成功')
    def do_rmdir(self,command,work_path):
        try:
            os.chdir(work_path)
            os.rmdir(command.split()[1])
        except Exception as e:
            self.send_train(str(e))
        else:
            self.send_train('删除成功')





    def do_ls(self,work_path):
        """
        将当前路径下的信息（文件名+文件大小）传送给客户端
        :return:
        """
        os.chdir(work_path)
        try:
            data = ''
            for file in os.listdir(os.getcwd()):
                data += file + '\t' + str(os.stat(file).st_size) + '\n'
            self.send_train(data.encode('utf8'))
        except Exception as e:
            self.send_train(str(e))

    def do_cd(self, command,work_path):
        """
        进入指定文件夹
        格式：cd+要进入的文件夹
        :param command:
        :return:
        """
        os.chdir(work_path)
        try:
            path = command.split()[1]
        except:
            self.send_train('请输入路径')
            return
        try:
            if len(command.split())>2:
                self.send_train('只能输入一个路径')
            else:
                try:
                    os.chdir(path)
                except:
                    self.send_train('命令错误')
                else:
                    if len(os.getcwd())<self.hide_len:
                        self.send_train('越界访问')
                    else:
                        self.path = os.getcwd()[self.hide_len:]
                        if self.path=='':
                            self.path='/'
                        self.send_train(self.path)
        except Exception as e:
            self.send_train(str(e))

    def do_pwd(self):
        """
        将当前路径返回给客户端
        :return:
        """
        self.send_train(self.path)
        print('self.send_train(self.path)')
    def do_rm(self, command,work_path,server_file_path):
        os.chdir(work_path)
        file_name=command.split()[1]
        try:
            md5_num = md5(file_name)
            os.remove(file_name)
        except Exception as e:
            self.send_train(str(e))
        else:
            # 得到该文件的引用值，如果为1，说明是最后一个，将记录删除
            # 如果不为1，则-1后更新
            count=conn.select2('sever_file','md5','count',md5_num)
            if count==1:
                conn.delete('sever_file','md5',md5_num)
                os.remove(server_file_path+'/'+file_name)
            else:
                new_count=count-1
                conn.update('sever_file','count',new_count,count)
            self.send_train('删除成功')

class Conn_Mysql:
    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.config = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": "utf8"
        }
        self.conn = connect(**self.config)
        self.cur = self.conn.cursor()

    def close(self):
        self.conn.close()
        self.cur.close()

    def insert(self, table_name, *args):
        """
        往指定的表中插入数据
        :param table_name:表名称
        :param args:要插入的数据
        :return:None
        """

        for item in args:
            sql = "INSERT INTO {} VALUES{};".format(table_name, item)
            self.cur.execute(sql)
            self.conn.commit()

    def select1(self, table_name, *args):
        """
        查询指定表中的数据，有返回1，没有返回0
        :param table_name:表名称
        :param args[0]:查询列名 arg[1]:查询元素
        :return:None
        """
        sql = "SELECT {} FROM {}; ".format(args[0], table_name)
        count = self.cur.execute(sql)
        for i in range(count):
            result = self.cur.fetchone()
            if args[1] in result:
                return 1
        return 0
    def select2(self,table_name,*args):
        """
        查询标中args[0]列等于args[2]的行中 arg[1]列的元素
        :param table_name:
        :param args:
        :return:
        """
        sql = "SELECT {}, {} FROM {} WHERE {}='{}'; ".format(args[0],args[1],table_name,args[0],args[2])
        self.cur.execute(sql)
        result=self.cur.fetchone()
        return result[1]

    def update(self, table_name, *args):
        """
        更新表中的数据
        :param table_name: 表名称
        :param args:
        :return:
        """
        sql = "UPDATE {} SET {}='{}' WHERE {}='{}';".format(table_name, args[0], args[1], args[0], args[2])
        self.cur.execute(sql)
        self.conn.commit()

    def delete(self, table_name, identify, *args):
        """
        删除指定表的指定数据
        :param table_name: 表名称
        :param args: 要删除的数据
        :return: None
        """

        for item in args:
            print(identify)
            print(item)
            sql = "DELETE FROM {} WHERE {}='{}';".format(table_name, identify, item)
            self.cur.execute(sql)
            self.conn.commit()



def do_gets(command,new_client,work_path):
    """
    发送客户端要下载的文件，发送大文件时不能一次行将文件读入内存，所以需要循环接收和循环发送
    发送方把文件名和文件大小发给接收方，接收方接收到发送过来的文件大小时接收完毕。
    :param command:
    :return:
    """
    os.chdir(work_path)
    file_name = command.split()[1]
    # 如果文件存在给客户端发1，否则发0
    try:
        f = open(file_name, 'rb')
    except:
        new_client.send(struct.pack('I', 0))
    else:
        new_client.send(struct.pack('I', 1))
        file_size = os.stat(file_name).st_size
        new_client.send(struct.pack('I', file_size))
        # 循环发送文件内容
        while True:
            file_content = f.read(10000)
            new_client.send(file_content)
            if not file_content:
                f.close()
                break
    new_client.close()

# md5算法
def md5(file_name):
    f = open(file_name, 'rb')
    f_md5 = hashlib.md5()
    f_md5.update(f.read())
    f.close()
    return (f_md5.hexdigest())


def do_puts(command:str,new_client,work_path,sever_file_path,user):
    os.chdir(work_path)
    file_name = command.split()[1]
    print('开始接收')
    new_md5_num=recv_train(new_client).decode('utf8')
    print('收到md5')
    print(new_md5_num)
    #文件中已经存在名字为file_name的文件,给客户端发0否则发1
    if file_name in os.listdir(os.getcwd()):
        new_client.send(struct.pack('I', 0))
    else:
        new_client.send(struct.pack('I', 1))
        if conn.select1('sever_file','md5',new_md5_num): #如果在数据库中
            print('在数据库中')
            # 通知客户端不用在进行文件传输
            new_client.send(struct.pack('I', 0))
            #根据md5值得到系统文件夹的文件名
            old_file_name=conn.select2('sever_file','md5','file_name',new_md5_num)
            #得到文件存放路径
            path=sever_file_path+'/'+old_file_name
            os.link(path,file_name)
            #得到原来的文件引用值
            count=conn.select2('sever_file','md5','count',new_md5_num)
            new_count=count+1
            # 更新文件的引用值
            conn.update('sever_file','count',new_count,count)
        else:
            # print('循环接收')
            new_client.send(struct.pack('I', 1))
            # 接收文件大小
            file_size = struct.unpack('I', new_client.recv(4))[0]
            #切换到系统统一保存文件的路径
            os.chdir(sever_file_path)
            # 循环接收文件内容
            f = open(file_name, 'wb')
            total = 0
            while True:
                file_content = new_client.recv(10000)
                f.write(file_content)
                total += len(file_content)
                if total == file_size:
                    f.close()
                    md5_num = md5(file_name)
                    # print('新加入的md5：%s'%md5_num)
                    # 将md5_num写入数据库
                    conn.insert('sever_file',(0,file_name,md5_num,1))
                    # 建立用户指向改系统路径下文件的硬连接
                    os.link(file_name,work_path+'/'+file_name)
                    break
        print('接收完毕')
        new_client.close()
# 删除path路径下的所有文件
def del_file(path):
    filelist=os.listdir(path)
    for file in filelist:
      file_path = os.path.join( path, file )
      if os.path.isfile(file_path):
        os.remove(file_path)
      elif os.path.isdir(file_path):
        shutil.rmtree(file_path)
# 路径的树形显示
def dfs_dir(path, width):
    global file_tree
    dir_list = os.listdir(path)
    for i in dir_list:
        file_tree+=' ' * width + i+'\n'
        if os.path.isdir(path + '/' + i):
            dfs_dir(path + '/' + i, width + 6)

# 获得token
def base_str():
    return (string.ascii_letters + string.digits)
def get_token():
    keylist = [random.choice(base_str()) for i in range(30)]
    return (''.join(keylist))
def send_train(data,client):
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
def recv_train(client):
    '''
    为防止数据粘包设计的协议
    根据send_train发送的字节流，解析出数据内容对应的字节流并返回
    :return:
    '''
    content_len = struct.unpack('I', client.recv(4))[0]
    return client.recv(content_len)
if __name__ == '__main__':
    conn = Conn_Mysql("192.168.74.128", 3306, "root", "123", "wangpan")
    server = Server('', 2000)
    server.task()

