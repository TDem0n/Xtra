import datetime, time

class timer:
    def __init__(self):
        self.startime = timer.gmtnow()
    @property
    def passed(self) -> datetime.timedelta:
        nowtime = timer.gmtnow()
        return nowtime - self.startime
    def gmtnow():
        """
        returns datetime object including current GMT time
        """
        return datetime.datetime.fromtimestamp(
            time.mktime(time.gmtime()),tz=datetime.timezone.utc)