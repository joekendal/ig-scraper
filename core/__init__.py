import threading

def threaded(function):
    """
    Used as a decorator to make function call threaded
    """
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=function, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper
