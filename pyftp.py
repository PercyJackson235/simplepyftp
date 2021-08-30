#!/home/user/PycharmProjects/simplepyftp/venv/bin/python3
import cmd
import socket
import getpass
from random import randint
import os
import time
import re
import tqdm
import select
import sys


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
            self.do_open(host)

    def do_user(self, arg: str = ''):
        """send new user information"""
        # sent as USER user and PASS password
        try:
            self.control_sock.getpeername()
        except OSError:
            return
        if arg == '':
            self.user = getpass.getuser()
            temp = input(f"Name ({self.host}:{self.user}): ").strip()
            if temp != '':
                self.user = temp
        else:
            self.user = arg
        self.control_sock.send(bytes(f"USER {self.user}\r\n", 'utf-8'))
        resp = self.control_sock.recv(1024).decode()
        print(resp)
        if resp.startswith('3'):
            self.password = getpass.getpass(prompt='Password: ').strip()
            self.control_sock.send(bytes(f"PASS {self.password}\r\n", 'utf-8'))
            print(self.control_sock.recv(1024).decode())
        else:
            return

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
                return
        try:
            self.control_sock.connect((self.host, self.port))
        except socket.gaierror as e:
            print(str(e))
            return
        print(self.control_sock.recv(1024).decode())
        self.do_system('')
        self.do_user('')

    def _portmath(self, port):
        """Calculating port coordinates. Accepts either a port number to
           be separated or a tuple of integers to be calculated together."""
        try:
            port = int(port)
        except (ValueError, TypeError):
            pass
        if isinstance(port, int):
            while True:
                p2 = randint(5, 235)
                temp = port - p2
                if temp % 256 == 0:
                    p1 = temp >> 8
                    return f"{p1},{p2}"
        else:
            try:
                port = list(map(int, port))
                return (port[0] << 8) + port[1]
            except ValueError as e:
                # Need to setup proper exception handling back up the stack
                print(str(e))
                raise ValueError(e)

    def do_sendport(self, arg):
        """toggle use of PORT cmd for each data connection.
           Not full implemented yet."""
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
            while True:
                try:
                    self._create_sock(active_ftp=True)
                    time.sleep(1)
                    ipadder = str(self.control_sock.getsockname()[0]).replace('.', ',')  # noqa: E501
                    ipadder += ',' + self._portmath(self.control_sock.getsockname()[1])  # noqa: E501
                    break
                except ValueError:
                    pass
            self.control_sock.send(bytes(f"PORT {ipadder}\r\n", 'utf-8'))
            print(self.control_sock.recv(1024).decode())
        else:
            address = None
            while address is None:
                self.control_sock.send(b"PASV\r\n")
                address = self.control_sock.recv(1024).decode().strip()
                regex = r'((\d{1,3},){4})(\d{1,3},\d{1,3})'
                address = re.search(regex, address).groups()
            port = (lambda x, y: (x * 256) + y)(*map(int, address[-1].split(',')))  # noqa: E501
            address = address[0].replace(',', '.').rstrip('.')
            self._create_sock(active_ftp=False, target=address, port=port)

    def _create_sock(self, active_ftp: bool, target=None, port: int = 0):
        self.data_sock = socket.socket()
        if active_ftp:
            while True:
                try:
                    self.data_sock.bind(('0.0.0.0', randint(40000, 60000)))
                    break
                except OSError:
                    pass
        else:
            self.data_sock.connect((target, port))

    def _file_stream(self, filename: str, get: bool = True, size: int = None):
        """File movement function"""
        chunk_size = 1024 * 1024
        try:
            if get:
                # Code in get used to be here
                with tqdm.tqdm(total=size) as pbar:
                    with open(filename, 'wb') as f:
                        while True:
                            chunk = self.data_sock.recv(chunk_size)
                            if chunk == b'':
                                break
                            pbar.update(f.write(chunk))
            else:
                chunk_size = 65000
                size = int(os.stat(filename).st_size)
                with tqdm.tqdm(total=size) as pbar:
                    with open(filename, 'rb') as f:
                        while True:
                            chunk = f.read(chunk_size)
                            if chunk == b'':
                                break
                            pbar.update(self.data_sock.send(chunk))
        except (FileNotFoundError, PermissionError, IsADirectoryError,
                IOError) as e:
            print(str(e))
            self._abort()
        finally:
            self.data_sock.close()

    def _data_stream(self):
        chunk_size = 1024 * 1024
        while True:
            try:
                conn = select.select([self.data_sock], [], [], 0.1)[0][0]
                chunk = conn.recv(chunk_size)
                if chunk == b'':
                    break
                print(chunk.decode())
            except IndexError:
                break
        self.data_sock.close()

    def _abort(self):
        """Send ABORT signal"""
        self.control_sock.send(b"ABOR\r\n")
        self.control_sock.recv(1024)

    def _data_connection(self, file=None, get=None, size: int = None):
        if file:
            self._file_stream(file, get, size)
        else:
            self._data_stream()

    def do_get(self, arg: str):
        """receive file"""
        try:
            remote_file, local_file = arg.split()
        except ValueError:
            remote_file = arg.strip()
            local_file = None
        if local_file is None:
            local_file = os.path.basename(remote_file)
        else:
            local_file = os.path.abspath(os.path.expanduser(local_file))
        self._create_data_conn()
        self.control_sock.send(f"SIZE {remote_file}\r\n".encode())
        size = int(self.control_sock.recv(1024).decode().strip().split()[-1])
        self.control_sock.send(bytes(f"RETR {remote_file}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())
        self._data_connection(file=local_file, get=True, size=size)
        print(self.control_sock.recv(1024).decode())

    def do_put(self, arg: str):
        """send one file"""
        try:
            local_file, remote_file = arg.split()
            print(local_file)
        except ValueError:
            print("ValueError")
            local_file = arg.strip()
            remote_file = None
        local_file = os.path.abspath(os.path.expanduser(local_file))
        if not os.path.exists(local_file):
            print(f"file {local_file} is does not exist!")
            return
        self._create_data_conn()
        if remote_file is None:
            sent_file = os.path.basename(local_file)
        else:
            sent_file = remote_file
        self.control_sock.send(f"STOR {sent_file}\r\n".encode())
        print(self.control_sock.recv(1024).decode())
        self._data_connection(file=local_file)
        print(self.control_sock.recv(1024).decode())

    def do_send(self, arg):
        """send one file"""
        self.do_put(arg)

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
        self._create_data_conn()
        self.control_sock.send(bytes(f"LIST {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())
        self._data_connection()
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
        self.do_disconnect('')

    def do_close(self, arg):
        """terminate ftp session"""
        if self.control_sock and self.control_sock.fileno() != -1:
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

    def do_size(self, arg):
        """show size of remote file"""
        self.control_sock.send(bytes(f"SIZE {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_pwd(self, arg):
        """print working directory on remote machine"""
        self.control_sock.send(b"PWD\r\n")
        print(self.control_sock.recv(1024).decode())

    def do_mkdir(self, arg):
        """create a directory on remote machine"""
        self.control_sock.send(bytes(f"MKD {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_rmdir(self, arg):
        """delete a directory on remote machine"""
        self.control_sock.send(bytes(f"RMD {arg}\r\n", 'utf-8'))
        print(self.control_sock.recv(1024).decode())

    def do_rhelp(self, arg):
        """get remote server help"""
        self.control_sock.send(b"HELP\r\n")
        print(self.control_sock.recv(1024))

    def do_quit(self, arg):
        """terminate ftp session"""
        self.do_disconnect('')
        return True

    def do_exit(self, arg):
        """terminate ftp session"""
        self.do_disconnect('')
        return True


if __name__ == "__main__":
    try:
        client = Client(host=sys.argv[1])
    except IndexError:
        client = Client()
    client.cmdloop()
