def threaded(function):
    """
    Used as a decorator to make function call threaded
    """
    def wrapper(*args, **kwargs):
        thread = threading.Thread(name=f'{args[0].type}Bot-{args[0].id}',target=function, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper


from .scraper import *
