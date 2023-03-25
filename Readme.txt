使用步骤
1、新建数据库名为 wangpan，通过mysql -u root -p <wangpan.sql导入数据库
2、修改wangpan_server.py的425行为自己的数据库信息
3、修改wangpan_client.py的192行为自己的服务器IP
4、然后在ubuntu上一个窗口python3 wangpan_sever.py启动服务器，另外一个窗口
python3 wangpan_client.py启动客户端即可使用，先注册，后登录