#!/home/user/PycharmProjects/simplepyftp/venv/bin/python3
import cmd
import socket
import getpass
import random
import os
import time
import re


class Client(cmd.Cmd):
    intro = 'Welcome to PyFTP!'
    prompt = 'pyftp> '

    def __init__(self, host=None, port=21, user='Anonymous', password='pass'):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.control_sock = socket.socket()
        self.data_sock = None
        self._port_cmd = False
        if host is not None:
            pass
            # self.do_open('')
            # self.do_user('')
        self.running = False

    def do_fake(self, fake):
        """Fake method for testing"""
        print("Calling do_fake and fake")
        a = self.fake(fake)
        print(a)

    def fake(self, fake):
        print("Doing fake")
        return fake[::-1]

    def do_user(self, arg: str = ''):
        """send new user information"""
        # sent as USER user and PASS password
        if arg == '':
            self.user = getpass.getuser()
            temp = input(f"Name ({self.host}:{self.user}): ").strip()
            if temp != '':
                self.user = temp
        else:
            self.user = arg
        self.password = getpass.getpass(prompt='Password: ').strip()
        print(f"USER {self.user}")
        print(f"PASS {self.password}")

    def do_cd(self, arg: str):
        """change remote working directory"""
        self.control_sock.send(bytes(f"CWD {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_lcd(self, arg: str):
        """change local working directory"""
        try:
            os.chdir(arg.strip())
        except FileNotFoundError:
            print(f"{arg} does not exist.")
        except NotADirectoryError:
            print(f"{arg} is not a directory.")
        except PermissionError:
            print(f"Do not have permission to change directory to {arg}")

    def do_shell(self, arg):
        """escape to the shell"""
        os.system(arg)

    def do_cdup(self, arg):
        """change remote working directory to parent directory"""
        self.control_sock.send("CDUP\r\n".encode())
        print(self.control_sock.recv(1024).decode())

    def do_open(self, arg=''):
        """connect to remote ftp server"""
        port = 21
        if arg == '':
            arg = input("(to) ").strip()
        try:
            host, port = arg.split()
            self.host = host
            self.port = int(port)
        except ValueError as e:
            if 'unpack' in str(e):
                if len(arg) == 0:
                    print('No Host Selected')
                else:
                    self.host = arg.strip()
                    self.port = port
            elif 'int' in str(e):
                print(f'{e} is invalid port')
        finally:
            print(self.host)
            print(self.port)
        if self.running:
            self.control_sock.connect((self.host, self.port))
            print(self.control_sock.recv(1024).decode())

    def _portmath(self, port):
        """Calculating port coordinates. Accepts either a port number to be separated or a tuple of integers to be
           calculated together."""
        try:
            port = int(port)
        except (ValueError, TypeError):
            pass
        if isinstance(port, int):
            while True:
                p2 = random.randint(5, 235)
                temp = port - p2
                if temp % 256 == 0:
                    p1 = temp >> 8
                    return f"{p1},{p2}"
        else:
            try:
                port = list(map(int, port))
                return (port[0] << 8) + port[1]
            except ValueError as e:
                print(str(e))  # Need to setup proper exception handling back up the stack

    def do_sendport(self, arg):
        """toggle use of PORT cmd for each data connection. Not full implemented yet."""
        if not self.running:
            return
        if arg != '':
            if arg.lower() == 'on':
                self._port_cmd = True
            elif arg.lower() == 'off':
                self._port_cmd = False
        else:
            self._port_cmd = not self._port_cmd
        print("Using PORT cmd" if self._port_cmd else "Using PASV cmd")

    def _create_data_conn(self):
        if self._port_cmd:
            self._create_sock(active_ftp=True)
            time.sleep(1)
            ipadder = str(self.control_sock.getsockname()[0]).replace('.', ',')
            ipadder += ',' + self._portmath(self.control_sock.getsockname()[1])
            self.control_sock.send(bytes(f"PORT {ipadder}\r\n"))
            print(self.control_sock.recv(1024).decode())
        else:
            self.control_sock.send(b"PASV\r\n")
            address = self.control_sock.recv(1024).decode().strip()
            address = re.search(r'((\d{1,3},){4})(\d{1,3},\d{1,3})', address).groups()
            port = (lambda x, y: (x * 256) + y)(*map(int, address[-1].split(',')))
            self._create_sock(active_ftp=False, target=address[0], port=port)

    def _create_sock(self, active_ftp: bool, target=None, port: int = 0):
        self.data_sock = socket.socket()
        if active_ftp:
            while True:
                try:
                    self.data_sock.bind(('localhost', random.randint(40000, 60000)))
                    break
                except OSError:
                    pass
        else:
            self.data_sock.connect((target, port))

    def do_get(self, arg):
        self.control_sock.send(bytes(f"RETR {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_binary(self, arg):
        """set binary transfer type"""
        self.control_sock.send(b'TYPE I\r\n')
        print(self.control_sock.recv(1024).decode())

    def do_image(self, arg):
        """set binary transfer type"""
        self.do_binary(None)

    def do_ascii(self, arg):
        """set ascii transfer type"""
        self.control_sock.send(b'TYPE A\r\n')
        print(self.control_sock.recv(1024).decode())

    def do_ls(self, arg: str = ''):
        """list contents of remote directory"""
        self.control_sock.send(bytes(f"LIST {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_dir(self, arg: str = ''):
        """list contents of remote directory"""
        self.do_ls(arg)

    def do_system(self, arg):
        """get system information"""
        self.control_sock.send(b"SYST\r\n")
        print(self.control_sock.recv(1024).decode())

    def do_bye(self, arg):
        """terminate ftp session and exit"""
        if self.running:
            self.do_disconnect('')

    def do_close(self, arg):
        """terminate ftp session"""
        self.control_sock.send(b"QUIT\r\n")
        print(self.control_sock.recv(1024).decode())
        self.control_sock.close()

    def do_disconnect(self, arg):
        """terminate ftp session"""
        self.do_close('')

    def do_delete(self, arg):
        """delete remote file"""
        self.control_sock.send(bytes(f"DELE {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_pwd(self, arg):
        self.control_sock.send(b"PWD\r\n")
        print(self.control_sock.recv(1024).decode())

    def do_quit(self, arg):
        """terminate ftp session"""
        print('QUIT')
        if self.running:
            self.do_disconnect('')
        return True


if __name__ == "__main__":
    client = Client()
    client.cmdloop()
