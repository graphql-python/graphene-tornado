from promise import Promise
from tornado.gen import convert_yielded, multi_future
from tornado.ioloop import IOLoop
from tornado.concurrent import is_future


# https://gist.github.com/isi-gach/daef0b34ec5af6f026af52d593131c64
class TornadoExecutor(object):
    def __init__(self, io_loop=None):
        if io_loop is None:
            io_loop = IOLoop.current()
        self.loop = io_loop
        self.futures = []

    def wait_until_finished(self):
        # if there are futures to wait for
        while self.futures:
            # wait for the futures to finish
            futures = self.futures
            self.futures = []
            self.loop.run_sync(lambda: multi_future(futures))

    def execute(self, fn, *args, **kwargs):
        result = fn(*args, **kwargs)
        if is_future(result):
            future = convert_yielded(result)
            self.futures.append(future)
            return Promise.resolve(future)
        return result
