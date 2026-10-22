"""Choose a free loopback port without stopping unrelated applications."""
import argparse,socket

def choose(preferred,start=19040,end=19140):
 for port in dict.fromkeys([preferred,*range(start,end+1)]):
  with socket.socket() as sock:
   try:sock.bind(('127.0.0.1',port))
   except OSError:continue
   return port
 raise RuntimeError('No free DigiMarketing loopback port in configured range')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('preferred',type=int);a=p.parse_args();print(choose(a.preferred))
