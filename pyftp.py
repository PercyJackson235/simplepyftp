#!/home/user/PycharmProjects/simplepyftp/venv/bin/python3
import cmd
import socket
import getpass
import random


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
        if host is not None:
            pass
            # self.do_open('')
            # self.do_user('')
        self.run = False

    def do_fake(self, fake):
        """Fake method for testing"""
        print(type(fake), fake)

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
        print(f"CWD {arg}")

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
        if self.run:
            self.control_sock.connect((self.host, self.port))
            print(self.control_sock.recv(1024).decode())

    def _portmath(self, port):
        """Calculating port coordinates. Accepts either a port number to be separated or a tuple of integers to be
           calculated together."""
        try:
            port = int(port)
        except ValueError:
            pass
        if isinstance(port, int):
            while True:
                p2 = random.randint(5, 235)
                temp = port - p2
                if temp % 256 == 0:
                    p1 = temp >> 8
                    return p1, p2
        else:
            try:
                port = list(map(int, port))
                return (port[0] << 8) + port[1]
            except ValueError as e:
                print(str(e))

    def do_quit(self, arg):
        """Exiting the Program."""
        print('QUIT')
        return True


if __name__ == "__main__":
    client = Client()
    client.cmdloop()
