"""Nonblocking host/project research lock; no ML or contest-runtime dependency."""
import errno
import json
import os

if os.name=='nt':
    import msvcrt
else:
    import fcntl


class ResearchLock:
    def __init__(self,path):
        self.path=path
        self.stream=None

    def acquire(self):
        if self.stream is not None:
            raise RuntimeError('Research lock is already acquired')
        descriptor=os.open(self.path,os.O_RDWR|os.O_CREAT|getattr(os,'O_BINARY',0),0o600)
        stream=os.fdopen(descriptor,'r+b')
        acquired=False
        try:
            stream.seek(0)
            try:
                if os.name=='nt':
                    # Locking beyond EOF is supported: acquire BEFORE any write.
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {errno.EACCES,errno.EAGAIN,errno.EDEADLK} or getattr(exc,'winerror',None)==33:
                    raise BlockingIOError(errno.EAGAIN,'Another owned research queue holds the training lock',str(self.path)) from exc
                raise
            acquired=True
            stream.seek(0,os.SEEK_END)
            if stream.tell()==0:
                stream.write(b' ')
                stream.flush()
            self.stream=stream
            return self
        except BaseException:
            try:
                if acquired:
                    self._unlock(stream)
            finally:
                stream.close()
            raise

    def write_identity(self,identity):
        if self.stream is None:
            raise RuntimeError('Research lock is not acquired')
        # Byte zero remains present and locked. Leading whitespace preserves JSON.
        payload=b' '+json.dumps(identity).encode('utf-8')
        self.stream.seek(0)
        self.stream.write(payload)
        self.stream.truncate(len(payload))
        self.stream.flush()

    @staticmethod
    def _unlock(stream):
        stream.seek(0)
        if os.name=='nt':
            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)

    def release(self):
        if self.stream is None:
            return
        stream,self.stream=self.stream,None
        try:
            self._unlock(stream)
        finally:
            stream.close()

    def __enter__(self):
        return self.acquire()

    def __exit__(self,exc_type,exc_value,traceback):
        self.release()
