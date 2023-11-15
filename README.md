# ENGG1003 Project

## Project description
After the pandemic, what happens to the Hong Kong Airport? How is the operation right now? Through this project, we will analyse the flight information of the Hong Kong Airport in real-time, to resolve the following problems:
1. What is the average / minimum / maximum / s.d. delay of the flights for the last 90 days?
2. What are the common destinations / origins of the flights?
3. Are longer routes generally have a longer delay?
4. Will flights arrived / departed at night have a longer delay?
5. Are there any increasing / decreasing trends of delays?
6. Which airline occupies the majority of flights in the Hong Kong airport? How much does it occupy?

## Known Issues (Though Won't Affect the Final Result)
1. HTTP Session sometimes isn't closed even when explicitly closing it. This might be issues with Jupyter Notebook (no issues if running as a .py script).
2. HTTP Requests can be slow depending on network speed / machine operating speed. For dynamic data retrieval, it may take up to 2 minutes to fetch all the data. 

## Data Retrieval
Data are obtained through API (instead of a static `.csv` file). The request path is https://www.hongkongairport.com/flightinfo-rest/rest/flights/past?date=&lang=en&cargo=false&arrival=false. There are four (mandatory) parameters:
1. Date (string): the date request for the flights in `YYYY-MM-DD` format.
2. Arrival (boolean): `true` if requesting for arrival flights (a.k.a. inbounding flights), or `false` if requesting for departure flights (a.k.a. outbounding flights).
3. Cargo (boolean): `true` if requesting for cargo flights, or `false` if not. We won't go deep into cargo flights in this project, so `false` will always be set in this project.
4. Lang (string): language of the data (only `en`, `zh_HK` and `zh_CN` is available). For the convenienve of data analysis `en` will always be set in this project.

For all the flights, some useful data are provided, including:
1. `time`: the estimated arrival time.
2. `status`: the current status of the flight. We only care about its arrival time this time.
3. `flight`: the aircraft invovled in this route and time. Flight number `no` and airline code `airline` are provided in each aircraft.
4. `destination / origin`: the destination(s) / origin(s) of the aircraft provided in IATA airport code. If there are multiple destinations / origins, it comes from / goes to each airport accordingly.

For the sake of convenience, we only consider data from `2023-08-17` to `2023-11-15`. In other words, data will not be dynamically fetched.

To fetch data, a `Fetcher` class is implemented:

And a `Flight` class is used for storing flights.


## Data Processing
Having API seems to make data processing easier, but actually not: though it gives JSON data, the data content is somewhat more likely to be read by humans instead of machines. Here is an abstract of the return data (i.e.: contents in the "list"):
```json
{
    "time": "23:20",
    "flight": [
        {
            "no": "UO 703",
            "airline": "HKE"
        }
    ],
    "status": "At gate 00:48 (28/10/2023)",
    "statusCode": null,
    "origin": [
        "BKK"
    ],
    ... (omitted not used data here)
}
```
`status` provides the actual arrival time and `time` provides the estimated arrival time. Here, the actual arrival time is not quite convenient to deal with: it has to split the actual status of the flight and arrival time separately, and it is necessary to determine the date of the estimated time since the API returns flights with estimated arrival date before the query date.

The aforementioned property also gives us another problem: if we query two consecutive dates, repeated data will be returned on each API call.

To resolve the first problem, some special processing is required:


The second problem is rather easy: dump all the data in a python set since set will remove duplicated elements.

To add a flight, we use the following statement:

Since set does not guarantee to be stored in a sorted way, we have to cast into a list and sort it before we return:

A full code view of the process data part:


Departure flights are similar to arrival flights. Only the processing part has some slight changes (e.g.: to check if the flight has departed, we check if the prefix of the status code is "Dep" instead of "At gate"; ).

## Question 1a: What are the statistics of delays of the flights?
After obtaining the flights, we can do a quick summarization by obtaining mean, median, mode, standard deviation, minimum and maximum.

### Analysing Process
1. Obtain the flights data and calculate the corresponding delays.
2. Calculate the statistics needed using module `statistics`.

### Mini-conclusion
1. Mean is around 6.89 minutes and 15.1 minutes (corrected to 3 siginificant figures), which is normal.
2. Both arrival and departure has a lesser median than mean. This signals that there are some flights with huge delay that pulls the mean up, while most of the data clusters in the middle.
3. Mode is surprisingly lower than 0 in arrival flights (-7 minutes) and 1 minute delay in departure flights.
4. Standard deviation is quite low and not spread out, compare with the minimum / maximum.

### Diagrams
These diagrams showcases the above conclusions.

## Question 1b: How can the distribution be curve-fitted to?
We may try to curve-fit with the above data. However, it didn't give some good results with even degree 10 polynomial regression.

We can instead bin the data. We will create a bin of size 5.



# References
1. https://www.hongkongairport.com/iwov-resources/misc/opendata/Flight_Information_DataSpec_en.pdf
2. https://github.com/ip2location/ip2location-iata-icao
3. https://stackoverflow.com/questions/74399077/python-display-loading-animation-while-preforming-a-long-task
4. https://pythonalgos.com/2021/12/26/send-api-requests-asynchronously-in-python/
5. https://stackoverflow.com/questions/47518874/how-do-i-run-python-asyncio-code-in-a-jupyter-notebook