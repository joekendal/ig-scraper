import threading

def threaded(function):
    """
    Used as a decorator to make function call threaded
    """
    def wrapper(*args, **kwargs):
        thread = threading.Thread(name=f'{args[0].type}Bot-{args[0].id}',target=function, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper


class colours:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
