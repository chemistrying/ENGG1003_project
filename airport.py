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
        
    async def fetch_airport_info(self):
        """
            Returns airport codes and its corresponding locations
        """
        import csv

        async with self.session.get("https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/master/all/all.csv") as response:
            text = await response.text()
            country_mapping = [row for row in csv.DictReader(text.split('\n'))]
            country_mapping = dict(
                zip(
                    [row["alpha-2"] for row in country_mapping],
                    [row["name"] for row in country_mapping]
                )
            )

        async with self.session.get("https://raw.githubusercontent.com/datasets/airport-codes/master/data/airport-codes.csv") as response:
            text = await response.text()
            airport_location = [row for row in csv.DictReader(text.split('\r\n'))]


        airport_info = {}
        for row in airport_location:
            if row["iata_code"]:
                try:
                    airport_info[row["iata_code"]] = dict(row | {"name": country_mapping[row["iso_country"]]})
                except:
                    # Fallback code
                    # Ignore errors
                    airport_info[row["iata_code"]] = dict(row | {"name": None})
                    pass

        return airport_info
    
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
    fixed_date: datetime = datetime(2023, 11, 14, 23, 59, 59, 0, timezone(timedelta(hours=8)))

    def __init__(self, loop, mode: Literal["static", "dynamic"] = "static"):
        self.client = Fetcher(loop, mode)

    def correct_data(self, delays, constant):
        """
            Correct the data by removing absoulted values larger than constant * s.d.
        """
        from statistics import stdev
        res = []
        sd = stdev(delays)
        for data in delays:
            if -constant * sd <= data and data <= constant * sd:
                res.append(data)
        return res

    def calculate_distance(self, src, dest):
        # Approximate radius of earth in km
        r = 6373.0

        from math import sin, cos, sqrt, asin, radians
        src_lat, src_lon = list(map(lambda v: radians(float(v)), src.split(", ")))
        dest_lat, dest_lon = list(map(lambda v: radians(float(v)), dest.split(", ")))
        
        dlat = dest_lat - src_lat
        dlon = dest_lon - src_lon

        return 2 * r * asin(sqrt(pow(sin(dlat / 2), 2) + cos(src_lat) * cos(dest_lat) * pow(sin(dlon / 2), 2)))

    async def fetch_arrival(self, interval: int, tz=8) -> list[Flight]:
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
        
    async def fetch_departure(self, interval: int, tz=8) -> list[Flight]:
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

class Question1(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)
            
    async def solver1(self, interval: int = 90, arrival: bool = True):
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
        
    async def solver2(self, interval: int = 90, arrival: bool = True):
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

        # fetch data
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        # calculate the delays of the flights in minutes
        delays = [int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60) for flight in flights]

        counter = {}
        for idx in range(min(delays), max(delays) + 1):
            counter[idx] = 0
        
        for delay in delays:
            counter[delay] += 1

        plt.bar(list(range(min(delays), max(delays) + 1)), list(counter.values()))
        
        plt.title("Flight Delay Distribution")
        plt.xlabel("Delay (in minutes)")
        plt.ylabel("Count")

    async def solver3(self, interval: int = 90, arrival: bool = True, bin_size: int = 5):
        """
            What if the data are binned?
            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        import matplotlib.pyplot as plt
        import numpy as np

        # fetch data
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        # calculate the delays of the flights in minutes
        delays = [int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60) for flight in flights]

        delays = self.correct_data(delays, 10)
        
        lb, rb = min(delays), max(delays)

        counts, bins = np.histogram(delays, list(range(lb, rb + bin_size, bin_size)))

        plt.hist(bins[:-1], bins, weights=counts)
        
        plt.title("Flight Delays Distribution (Binned)")
        plt.xlabel("Delay (in minutes)")
        plt.ylabel("Count")

class Question2(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)

    async def solver1(self, interval: int = 90, arrival: bool = True):
        """
            Problem: What are the common destination / origin of flights for the past 90 days?

            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        import cartopy.crs as ccrs
        import cartopy.io.shapereader as shpreader
        import cartopy.feature as cf
        import matplotlib.pyplot as plt
        import matplotlib as mpl

        cmap = mpl.colormaps.get_cmap('tab20')

        airport_info = await self.client.fetch_airport_info()
        
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        ax = plt.axes(projection=ccrs.PlateCarree())
        countries_shp = shpreader.natural_earth(resolution='10m',
                                            category='cultural', name='admin_0_countries')
        special_regions_shp = shpreader.natural_earth(resolution='10m',
                                                      category='cultural', name='admin_0_map_units')
        taiwan_shp = shpreader.natural_earth(resolution='10m',
                                                      category='cultural', name='admin_0_disputed_areas')
        
        country_counter = dict.fromkeys(
            list(map(lambda v: v.attributes['WB_A2'], shpreader.Reader(countries_shp).records())) +
            list(map(lambda v: v.attributes['WB_A2'], shpreader.Reader(special_regions_shp).records())) + ['TW'],
            0
        )

        # Mark down the flight origin / destination
        for flight in flights:
            destinations = flight.airports
            for dest in destinations:
                # this is the country that the airport belongs to: airport_info[dest]["name"]
                country_counter[airport_info[dest]["iso_country"]] += 1
        
        maximo = max(country_counter.values())
        
        visited = dict.fromkeys(
            list(map(lambda v: v.attributes['WB_A2'], shpreader.Reader(countries_shp).records())) +
            list(map(lambda v: v.attributes['WB_A2'], shpreader.Reader(special_regions_shp).records())) + ['TW'],
            False
        )
        
        # Loop normal countries
        for country in shpreader.Reader(countries_shp).records():
            nome = country.attributes['WB_A2']
            if visited[nome]:
                continue
            else:
                visited[nome] = True
            
            numero = country_counter[nome]
            if numero != 0:
                ax.add_geometries(country.geometry, ccrs.PlateCarree(),
                            facecolor=cmap(numero / float(maximo), 1),
                            label=nome)

        # Loop small regions
        for country in shpreader.Reader(special_regions_shp).records():
            nome = country.attributes['WB_A2']
            if visited[nome]:
                continue
            else:
                visited[nome] = True

            numero = country_counter[nome]
            if numero != 0:
                ax.add_geometries(country.geometry, ccrs.PlateCarree(),
                            facecolor=cmap(numero / float(maximo), 1),
                            label=nome)
        
        # Special handle Taiwan
        for country in shpreader.Reader(taiwan_shp).records():
            if (country.attributes['NAME_LONG'] == "Taiwan"):
                # print(country.attributes)
                nome = 'TW'
                numero = country_counter[nome]
                if numero != 0:
                    ax.add_geometries(country.geometry, ccrs.PlateCarree(),
                                facecolor=cmap(numero / float(maximo), 1),
                                label=nome)
                break
        
        # Add coastlines and borders
        ax.coastlines()
        ax.add_feature(cf.BORDERS)

        plt.colorbar(mpl.cm.ScalarMappable(cmap=cmap), ax=ax)
        plt.title(f"Common {'Origins' if arrival else 'Destinations'} of Flights {'from' if arrival else 'to'} Hong Kong")

    async def solver2(self, interval: int = 90, arrival: bool = True):
        """
            Problem: What if we visualize the data in bar chart? We only visulalize top 10 destinations / origins.

            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        import matplotlib.pyplot as plt

        airport_info = await self.client.fetch_airport_info()
        
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)
        
        country_counter = dict.fromkeys(
            [airport_info[country]["name"] for country in airport_info],
            0
        )

        # Mark down the flight origin / destination
        for flight in flights:
            destinations = flight.airports
            for dest in destinations:
                # this is the country that the airport belongs to: airport_info[dest]["name"]
                country_counter[airport_info[dest]["name"]] += 1

        arr = sorted(country_counter.items(), key=lambda v: v[1])[-20:]
        keys = list(map(lambda v: v[0], arr))
        values = list(map(lambda v: v[1], arr))

        plt.title(f"Number of Flights {'from' if arrival else 'to'} Hong Kong Group by {'Origin' if arrival else 'Destination'}")
        plt.barh(keys, values)
        plt.xlabel("Country")
        plt.ylabel("Flight Count")

    async def solver3(self, interval: int = 90, arrival: bool = True):
        """
            Problem: What if we group by continents?

            Parameters
            ----------
            interval: int
                The number of days to be checked.
            arrival: bool
                True if asking for arrival flights, else asking for departure flights
        """
        import matplotlib.pyplot as plt

        airport_info = await self.client.fetch_airport_info()
        
        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)
        
        country_counter = dict.fromkeys(
            [airport_info[country]["continent"] for country in airport_info],
            0
        )

        # Mark down the flight origin / destination
        for flight in flights:
            destinations = flight.airports
            for dest in destinations:
                # this is the country that the airport belongs to: airport_info[dest]["name"]
                country_counter[airport_info[dest]["continent"]] += 1

        continent_long_name = {
            "EU": "Europe",
            "SA": "South America",
            "AN": "Antarctica",
            "AS": "Asia",
            "AF": "Africa",
            "NA": "North America",
            "OC": "Oceania"
        }

        plt.title(f"Number of Flights {'from' if arrival else 'to'} Hong Kong Group by {'Origin' if arrival else 'Destination'}")
        plt.barh(list(map(lambda v: continent_long_name[v], country_counter.keys())), list(country_counter.values()))
        plt.xlabel("Country")
        plt.ylabel("Flight Count")

class Question3(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)

    async def solver(self, interval: int = 90, arrival: bool = True):
        import matplotlib.pyplot as plt
        import numpy as np

        airport_info = await self.client.fetch_airport_info()

        hkg = airport_info["HKG"]

        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        dists = []
        delays = []
        for flight in flights:
            target_airport = airport_info[flight.airports[0]]
            # Only consider the FIRST destination
            dist = self.calculate_distance(target_airport["coordinates"] if arrival else hkg["coordinates"], hkg["coordinates"] if arrival else target_airport["coordinates"])
            delay = int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60)

            if delay >= 300:
                dists.append(dist)
                delays.append(delay)

        # counts, bins = np.histogram(dists, list(range(0, 20000, 2000)))
        # plt.hist(bins[:-1], bins, weights=counts)
        plt.scatter(dists, delays)

        plt.title("Distance Against Number of Flights That Have a Delay Larger Than 300 Minutes")
        plt.xlabel("Distance (in kilometers)")
        plt.ylabel("Delay (in minutes)")

class Question4(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)

    async def solver(self, interval: int = 90, arrival: bool = True):
        import matplotlib.pyplot as plt

        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        times = []
        delays = []
        for flight in flights:
            est_time = datetime.fromisoformat(flight.est_time)
            clock = est_time.time()
            time_from_zero = clock.hour * 3600 + clock.minute * 60 + clock.second
            delay = int((datetime.fromisoformat(flight.act_time) - datetime.fromisoformat(flight.est_time)).total_seconds() // 60)

            times.append(time_from_zero)
            delays.append(delay)

        plt.scatter(times, delays)
        plt.xlabel("Estimated Arrival Time Away from 00:00 (in minutes)")
        plt.ylabel("Delays (in minutes)")
        
class Question5(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)

    async def solver(self, interval: int = 90, arrival: bool = True):
        import matplotlib.pyplot as plt
        import numpy as np

        airport_info = await self.client.fetch_airport_info()

        hkg = airport_info["HKG"]

        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        dists = []
        for flight in flights:
            target_airport = airport_info[flight.airports[0]]
            # Only consider the FIRST destination
            dist = self.calculate_distance(target_airport["coordinates"] if arrival else hkg["coordinates"], hkg["coordinates"] if arrival else target_airport["coordinates"])
            dists.append(dist)

        counts, bins = np.histogram(dists, list(range(0, 20000, 2000)))
        plt.hist(bins[:-1], bins, weights=counts)

        plt.xlabel("Distance (in kilometers)")
        plt.ylabel("Flight Count")
            
# class Question6(FlightAnalyser):
#     def __init__(self, loop):
#         super().__init__(loop)

#     async def solver(self, interval: int = 90, arrival: bool = True):
#         import matplotlib.pyplot as plt

#         cmap = plt.get_cmap("plasma")
#         pairer = {
#             "EU": 0,
#             "SA": 0.126,
#             "AN": 0.251,
#             "AS": 0.376,
#             "AF": 0.501,
#             "NA": 0.626,
#             "OC": 0.751
#         }

#         airport_info = await self.client.fetch_airport_info()

#         hkg = airport_info["HKG"]

#         flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

#         for continent in pairer:
#             dists = []
#             times = []
#             for flight in flights:
#                 # Only consider the FIRST destination
#                 target_airport = airport_info[flight.airports[0]]
#                 if target_airport["continent"] == continent:
#                     dist = self.calculate_distance(target_airport["coordinates"] if arrival else hkg["coordinates"], hkg["coordinates"] if arrival else target_airport["coordinates"])
                    
#                     est_time = datetime.fromisoformat(flight.act_time)
#                     clock = est_time.time()
#                     time_from_zero = clock.hour * 3600 + clock.minute * 60 + clock.second
                    
#                     dists.append(dist)
#                     times.append(time_from_zero)
#                     dists.append(dist)
#                     times.append(time_from_zero + 24 * 3600)
#             plt.scatter(times, dists, color=cmap(pairer[continent], 1))
        
#         plt.xlabel("Estimated Arrival Time away from 00:00 (in minutes)")
#         plt.ylabel("Distance (in kilometers)")

class Question6(FlightAnalyser):
    def __init__(self, loop):
        super().__init__(loop)

    async def solver1(self, interval: int = 90, arrival: bool = True):
        import matplotlib.pyplot as plt

        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        timeslots = [0] * 24 * 90

        for flight in flights:
            est_time = datetime.fromisoformat(flight.est_time)

            hour = est_time.hour
            day = interval - (self.fixed_date.date() - est_time.date()).days - 1
            timeslots[day * 24 + hour] += 1

        plt.plot(list(range(24 * 90)), timeslots)
        
        plt.xlabel("Timeslot (Delta hour from 2023-08-17 00:00)")
        plt.ylabel("Flight Count")

    async def solver2(self, interval: int = 90, arrival: bool = True):
        import matplotlib.pyplot as plt
        import numpy as np

        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        timeslots = [0] * 24 * interval

        for flight in flights:
            est_time = datetime.fromisoformat(flight.act_time)

            hour = est_time.hour
            day = interval - (self.fixed_date.date() - est_time.date()).days - 1
            timeslots[day * 24 + hour] += 1

        x = list(range(24))
        y = [sum([timeslots[i] for i in range(x, 24 * interval, 24)]) / interval for x in range(24)]
        plt.plot(x, y)

        mymodel = np.poly1d(np.polyfit(x, y, 12))
        myline = np.linspace(0, 23, 100)
        plt.plot(myline, mymodel(myline), color="red")

        plt.xlabel("Timeslot (Delta hour from 2023-08-17 00:00)")
        plt.ylabel("Flight Count")

    async def solver3(self, interval: int = 90, arrival: bool = True, skip_date: str = "2023-08-17"):
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        flights = await self.fetch_arrival(interval) if arrival else await self.fetch_departure(interval)

        timeslots = [0] * 24 * interval

        actual_data = [0] * 24
        for flight in flights:
            est_time = datetime.fromisoformat(flight.act_time)
            hour = est_time.hour

            if datetime.fromisoformat(flight.act_time).date().isoformat() == skip_date:
                actual_data[hour] += 1
            else:
                day = interval - (self.fixed_date.date() - est_time.date()).days - 1
                timeslots[day * 24 + hour] += 1

        x = list(range(24))
        y = [sum([timeslots[i] for i in range(x, 24 * interval, 24)]) / (interval - 1) for x in range(24)]
        
        plt.bar(x, actual_data)

        plt.xlabel("Timeslot (Delta hour from 2023-08-17 00:00)")
        plt.ylabel("Flight Count")

        mymodel = np.poly1d(np.polyfit(x, y, 12))
        myline = np.linspace(0, 23, 24)

        estimated_data = list(map(round, mymodel(myline)))
        error = [estimated_data[x] - actual_data[x] for x in range(24)]

        plt.plot(myline, estimated_data, color="red")

        df = pd.DataFrame(
            {
                "Estimated Data" : estimated_data,
                "Actual Data" : actual_data,
                "Error" : error
            }
        )
        print(df)
        print(f"Average Error: {sum(error) / len(error)}")