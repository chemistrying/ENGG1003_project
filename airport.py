import json
from datetime import *
import aiohttp
import aiofiles
from typing import Literal

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__

class Fetcher:
    url = "https://www.hongkongairport.com/flightinfo-rest/rest/flights/past?date={date}&lang=en&cargo=false&arrival={arrival}"
    session: aiohttp.ClientSession
    mode: Literal["static", "dynamic"]

    def __init__(self, loop, mode: Literal["static", "dynamic"] = "static"):
        self.session = aiohttp.ClientSession(loop=loop)
        self.mode = mode
        pass

    async def __static_fetch_arival(self, date):
        async with aiofiles.open(f"arrival\\{date.strftime('%Y-%m-%d')}.json", mode="r") as f:
            data = await f.read()
            return json.loads(data)
    
    async def __static_fetch_departure(self, date):
        async with aiofiles.open(f"departure\\{date.strftime('%Y-%m-%d')}.json", mode="r") as f:
            data = await f.read()
            return json.loads(data)
        
    async def __dynamic_fetch_arrival(self, date):
        async with self.session.get(self.url.format(date=date.strftime("%Y-%m-%d"), arrival="true")) as response:
            text = await response.text()
            return json.loads(text)
    
    async def __dynamic_fetch_departure(self, date):
        async with self.session.get(self.url.format(date=date.strftime("%Y-%m-%d"), arrival="false")) as response:
            text = await response.text()
            return json.loads(text)
    
    async def fetch_arrival(self, date):
        """
            Returns flights that its estiamted arrival date is equal to this specific date
        """
        if self.mode == "static":
            res = await self.__static_fetch_arival(date)
            return res
        else:
            res = await self.__dynamic_fetch_arrival(date)
            return res
    
    async def fetch_departure(self, date):
        """
            Returns flights that its actual departure time or estimated departure time is equal to this specific date
        """
        if self.mode == "static":
            res = await self.__static_fetch_departure(date)
            return res
        else:
            res = await self.__dynamic_fetch_departure(date)
            return res
    
    async def close(self):
        await self.session.close()

class FlightIdentifier:
    flight_number: str
    airline: str

    def __init__(self, flight_number, airline):
        self.flight_number = flight_number
        self.airline = airline

class Flight:
    arrival: bool # is this flight an arrival flight
    est_time: str # estimated arrival / departure time in ISO format
    act_time: str # actual arrival / departure time in ISO format
    airports: list[str] # list of airport(s) that the flight come from / go to
    flight_code: list[FlightIdentifier]

    def __init__(self, arrival: bool, est_time: str, act_time: str, airports: list[str], flight_code: list[FlightIdentifier]):
        self.arrival = arrival
        self.est_time = est_time # need to use ISO 8601 here
        self.act_time = act_time # same as above
        self.airports = airports
        self.flight_code = [FlightIdentifier(x["no"], x["airline"]) for x in flight_code]
    
    """
        Some operator overloading magic down here
    """

    def __lt__(self, other):
        return datetime.fromisoformat(self.act_time) < datetime.fromisoformat(other.act_time)
    
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        """
            This hash function is meant to be used for storing things in a set
        """
        return hash((self.arrival, self.est_time, self.act_time, '-'.join(self.airports), ';'.join([fc.flight_number for fc in self.flight_code])))

class FlightAnalyser:
    interval: int # The interval to be checked
    timezone: int # offset from utc
    client: Fetcher
    fixed_date: date = datetime(2023, 11, 14, 23, 59, 59, 0, timezone(timedelta(hours=8)))

    def correct_data(self, delays: list[int], threshold=6) -> list[int]:
        from statistics import stdev, mean
        from math import floor, ceil
        sd = stdev(delays)
        mn = mean(delays)
        lb, rb = floor(mn - threshold * sd), ceil(mn + threshold * sd)

        res = []
        for delay in delays:
            if lb <= delay and delay <= rb:
                res.append(delay)
        return res


    def __init__(self, loop, mode: Literal["static", "dynamic"] = "static"):
        self.client = Fetcher(loop, mode)

    async def fetch_arrival(self, interval: int, tz=8):
        """
            Fetches arrival flights and organize the data obtained
        """
        # only check flights between lower bound and upper bound
        # only returns flights which have arrived
        flights = set()
        today = self.fixed_date if self.client.mode == "static" else datetime.now(timezone(timedelta(hours=tz)))
        lower_bound = today - timedelta(days=interval)
        upper_bound = today
        for curr_date in [lower_bound.date() + timedelta(days=i) for i in range(interval + 1)]:
            # obtain data from api
            data = await self.client.fetch_arrival(curr_date)
            for datum in data:
                # ignore data which its date does not match query date - those data should have been obtained from previous queries
                if datum["date"] != curr_date.isoformat():
                    continue
                
                # iterate each flight group
                for group in datum["list"]:
                    # construct the estimated time (no date)
                    est_time = datetime.fromisoformat(f"{curr_date}T{group['time']}:00+08:00")

                    # tokenize the status
                    status_code = group["status"].split()

                    # only consider data with status "At gate"
                    if len(status_code) >= 3 and status_code[0] + ' ' + status_code[1] == "At gate":
                        # ok
                        if len(status_code) == 4:
                            # special case: the estimated time and actual time lies on different date
                            # need extract the date from the status code
                            temp_date = list(map(int, status_code[-1][1:-1].split('/')))
                            required_date = date(temp_date[2], temp_date[1], temp_date[0]) # this converts the date string given to date object

                            # construct the actual datetime
                            act_time = datetime.fromisoformat(f"{required_date}T{status_code[2]}:00+08:00")
                        else:
                            # both datetime lies on the same date - less work to handle
                            act_time = datetime.fromisoformat(f"{curr_date}T{status_code[2]}:00+08:00")

                        # determine if the time actually lies on the interval we are searching
                        if lower_bound <= act_time and act_time <= upper_bound:
                            # add to the entry
                            flights.add(Flight(True, est_time.isoformat(), act_time.isoformat(), group["origin"], group["flight"]))
            
        # sort the flights in actual arrival time chornological order 
        flights = sorted(list(flights))
        return flights
        
    async def fetch_departure(self, interval: int, tz=8):
        """
            Fetches departure flights and organize the data obtained
        """
        # only check flights between lower bound and upper bound
        # only returns flights which have departed
        # code is similar to analyse_arrival but with slight changes on cleansing data part
        flights = set()
        today = self.fixed_date if self.client.mode == "static" else datetime.now(timezone(timedelta(hours=tz)))
        lower_bound = today - timedelta(days=interval)
        upper_bound = today
        for curr_date in [lower_bound.date() + timedelta(days=i) for i in range(interval + 1)]:
            # obtain data from api
            data = await self.client.fetch_departure(curr_date)
            for datum in data:
                if datum["date"] != curr_date.isoformat():
                    continue
                
                for group in datum["list"]:
                    est_time = datetime.fromisoformat(f"{curr_date}T{group['time']}:00+08:00")

                    status_code = group["status"].split()

                    # only consider data with status "Dep"
                    # print(status_code)
                    if len(status_code) >= 2 and status_code[0] == "Dep":
                        # ok
                        if len(status_code) == 3:
                            # cleanse the date to ISO format
                            temp_date = list(map(int, status_code[-1][1:-1].split('/')))
                            required_date = date(temp_date[2], temp_date[1], temp_date[0])

                            act_time = datetime.fromisoformat(f"{required_date}T{status_code[1]}:00+08:00")
                        else:
                            act_time = datetime.fromisoformat(f"{curr_date}T{status_code[1]}:00+08:00")
                            
                        if (lower_bound <= act_time and act_time <= upper_bound) or self.client.mode == "static": # ignore date bounding when in static mode
                            # add to the entry
                            flights.add(Flight(False, est_time.isoformat(), act_time.isoformat(), group["destination"], group["flight"]))
            
        flights = sorted(list(flights))
        return flights
    
    async def finish(self):
        await self.client.close()
    

        '''
        lb = min(delays) - min(delays) % bin_size
        rb = max(delays) + (bin_size - max(delays) % bin_size) % bin_size + 1

        counts, bins = np.histogram(delays, bins=list(range(lb, rb, bin_size)))
        for i in range(len(counts)):
            if counts[i] < threshold:
                counts[i] = 0
        
        update_flag = False
        ulb = 0x3f3f3f3f
        urb = 0x3f3f3f3f
        for i in range(len(counts)):
            if counts[i]:
                urb = i + 1
                rb = bins[i] + bin_size + 1
                if not update_flag:
                    ulb = i
                    lb = bins[i]
                    update_flag = True


        if ulb == urb and ulb == 0x3f3f3f3f:
            raise ValueError("Threshold too large, can't display anything")
    
        counts = counts[ulb:urb]
        bins = bins[ulb:urb + 1]

        # x = list(range(lb, rb))
        # y = list(map(lambda p: 0 if counter[p] < threshold else counter[p], counter))
        # sample_points = list(map(lambda t: list(t), list(zip(x, y))))
        
        # model = np.poly1d(np.polyfit(x, y, 20))
        # line = np.linspace(lb, rb, 1000)

        # df = pd.DataFrame({
        #     "minute(s)": list(range(lb, rb)),
        #     "count": list(map(lambda x: counter[x], counter))
        # })
        # print(df)
        # df.plot(x="minute(s)", y="count", kind="line")

        # plt.plot(x, y, color="blue")
        # plt.hist(delays, bins=list(range(lb, rb, bin)))
        # plt.plot(line, model(line), color="red")
        # print("OK")
        plt.hist(bins[:-1], bins, weights=counts)
        # quantiles = statistics.quantiles(delays, 10)
        
        popper = []
        for i in range(len(delays)):
            if delays[i] not in range(lb, rb):
                # print(delays[i])
                popper.append(delays[i])
        for item in popper:
            delays.remove(item)


        
        norm_func = statistics.NormalDist.from_samples(delays)
        print(norm_func.stdev, norm_func.mean, norm_func.median, statistics.median(delays), statistics.mean(delays), statistics.stdev(delays))
        plt.plot(list(range(lb, rb, bin_size)), list(map(lambda v: len(delays) * norm_func.pdf(v), list(range(lb, rb, bin_size)))), color="red")

        plt.xlabel("minute(s)")
        plt.ylabel("count")
        '''
class Question1(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)
            
    async def solver1(self, interval: int, arrival: bool):
        """
            Problem: What are the statistics of delays of the flights for the last 90 days?

            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        from statistics import mean, median, mode, stdev
        import pandas as pd

        # fetch data
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        # calculate the delays of the flights in minutes
        delays = [int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60) for flight in flights]

        print(f"\rStatistics for Delays of {'Arrival' if arrival else 'Departure'} Flights")

        df = pd.DataFrame(
            {
                "Statistics": ["Mean", "Median", "Mode", "S.D.", "Min", "Max"],
                "Values": [mean(delays), median(delays), mode(delays), stdev(delays), min(delays), max(delays)]
            }
        )

        print(df)
        
    async def solver2(self, interval: int, arrival: bool):
        """
            Problem: Output the diagram of the data.

            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        import matplotlib.pyplot as plt
        from statistics import NormalDist

        # fetch data
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        # calculate the delays of the flights in minutes
        delays = [int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60) for flight in flights]

        counter = {}
        for idx in range(min(delays), max(delays) + 1):
            counter[idx] = 0
        
        for delay in delays:
            counter[delay] += 1

        plt.plot(list(range(min(delays), max(delays) + 1)), list(counter.values()))
        
        norm_func = NormalDist.from_samples(delays)
        plt.plot(
            list(range(min(delays), max(delays) + 1)), 
            list(map(
                lambda v: len(delays) * norm_func.pdf(v), 
                list(range(min(delays), max(delays) + 1))
            )), 
            color="red"
        )

    async def solver3(self, interval: int, arrival: bool, bin_size: int = 10):
        """
            Problem: If outliers are removed, how would be the diagram look? Define outliers > mean + (5 sd) or < mean - (5 sd) 

            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        import matplotlib.pyplot as plt
        from statistics import stdev, mean, median, mode, NormalDist
        from math import ceil, floor
        import pandas as pd
        import numpy as np

        # fetch data
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        # calculate the delays of the flights in minutes
        delays = [int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60) for flight in flights]

        delays = self.correct_data(delays, 10)
        
        lb, rb = min(delays), max(delays)

        counts, bins = np.histogram(delays, list(range(lb, rb + bin_size, bin_size)))
        avg_bins = [(bins[i] + bins[i + 1]) / 2 for i in range(len(bins) - 1)]

        plt.hist(bins[:-1], bins, weights=counts)
        
        binned_data = []
        for i in range(len(bins) - 1):
            avg = (bins[i] + bins[i + 1]) / 2
            binned_data += [avg] * counts[i]

        norm_func = NormalDist.from_samples(binned_data)
        plt.plot(
            list(range(min(delays), max(delays) + 1)), 
            list(map(
                lambda v: len(binned_data) * norm_func.pdf(v), 
                list(range(min(delays), max(delays) + 1))
            )), 
            color="red"
        )

        # model = np.poly1d(np.polyfit(avg_bins, counts, 4))
        # line = np.linspace(min(delays), max(delays), 1000)

        # plt.plot(line, model(line))










