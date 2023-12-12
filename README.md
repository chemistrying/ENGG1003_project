# ENGG1003 Project

## Project description
After the pandemic, what happens to the Hong Kong Airport? How is the operation right now? Through this project, we will analyse the flight information of the Hong Kong Airport in real-time, to resolve the following problems:
1. What is the average / minimum / maximum / s.d. delay of the flights for the last 90 days?
2. What are the common destinations / origins of the flights?
3. Are longer routes generally have a longer delay?
4. Will flights arrived / departed at night have a longer delay?
5. Do longer routes have generally less flights?
6. What are the flight frequency in a day?

## Used Modules
This projects uses `aiohttp` (for data fetching), `matplotlib` (for data visualization), `pandas` (for using dataframe), `cartopy` (for globe visualization), `numpy` (for regression).

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
1. Mean is around 6.89 minutes and 15.1 minutes (corrected to 3 siginificant figures), which is slightly higher than expectation (imagine having an average delay of 15 minutes per flight!).
2. Both arrival and departure has a lesser median than mean. This signals that there are some flights with huge delay that pulls the mean up, while most of the data clusters in the middle.
3. Mode is surprisingly lower than 0 in arrival flights (-7 minutes) and 1 minute delay in departure flights.
4. Standard deviation is quite low and not spread out, compare with the minimum / maximum.

### Diagrams
These diagrams showcases the above conclusions.
If the data are binned, we can see the results more clearly.

## Question 2a: What are the most common destinations of the flights?
By using the destination / origins info given by the data, we can analyse the common destinations / origins of the flights, thus analysing how frequent the flights between each countries are. We will visualize the data with heatmaps.

### Analysis Process
1. Obtain the flight data.
2. Count the number of flights that go to the specific destination and map to its corresponding belonging country.
3. Visualize the data through world heat map. The value of each country lies in the range $[0.0, 1.0]$, and is determined by the count of flights divded by maximum of count of flights amongst all countries. The values are quantized by bins of size $0.1$.

### Mini-conclusion
1. The arrival flights and departure flights gives almost the same result (because a flight is usually a round trip, i.e.: it departs at Hong Kong to another destination and come back to Hong Kong).
2. The most common flights are from/to China, which is in our expectation because most common origin of visitors of Hong Kong are people from Mainland China.
3. Taiwan and Japan has also a lot of flights (above $0.4$) compare to other countries, possibly because Hongkongers prefer visiting these places.
4. Philippines has a value of $0.2$, higher than most of the countries (most countries lies in the range $[0.0, 0.2)$), which is out of my expectation: Hong Kong tourism doesn't mainly compose of people from Philippines, and it is not a common tourism hotspot in Hong Kong either. This may possibly because of the composition of Hong Kong foreign domestic helpers are mostly from the Phillippines, and so there are demands of flights between Hong Kong and the Phillippines. The demand was larger than tourism to European and American destinations.
5. There are almost no flights to South America. However, the question of if there are no flights to South America has to be confirmed with later analysis (since the blue spot appeared actually belongs to France).

## Question 2b: What if we visualize our data using bar charts?
We now have grasped the general idea of common destinations. If we visualize our data with bar charts, we can firmly confirm our conclusions made above.

### Analysis Process
The process is same as the one above. However, we have one more method of grouping: group by continent. Note: I personally wish to analyse by grouping small regions as well, but due to the fact the mapping of ISO 3166-2 code is impossible without buy the data (though can be scrapped in the internet but somehow this is stealing data), we won't perform the analysis of that here.

### Mini-conclusion
1. Among all top 20 countries / regions, 13 of them are from Asia (this means Asian countries occupies most of the flights, as shown when flights are being grouped in continents)
2. There are no flights to Antarctica (normal) and South America (a surprising observation!).

## Question 3: Are longer routes generally have a longer delay?
To answer this question, we first have to know how to calculate distance between two spots. 

Since we have the latitude and longitude of the airports, we can calculate using the formula suggested by Wikipedia:
$$ d = 2r \arcsin \left (\sqrt{\sin^2 \left(\frac{\varphi_2 - \varphi_1}{2}\right) + \cos \varphi_1 \cdot \cos \varphi_2 \cdot \sin^2 \left(\frac{\lambda_2 - \lambda_1}{2} \right)} \right) $$
Where $r$ is the radius of the sphere (in this case the Earth).

It doesn't matter if we understand the formula or not, cuz neither do I :)

So after using this, let's plot a scatter plot and see the result.

### Mini-conclusion
There are no relationships between delays and distance.

## Question 4: Will flights arrived / departed at night have a longer delay?
We will plot the estimated arrival time (ignore date, only consider clock time) as x-axis and delay (in minutes) as y-axis.

## Mini-conclusion
It doesn't matter. Delays can happen at anytime in a day.

## Question 5: Do longer routes have generally less flights?
We will now plot a histogram with distance as x-axis and flight count as y-axis.

## Mini-conclusion
The assumption is partially true: there are more shorter flights than longer flights, but it doesn't strictly decrease as the distance increases. 

## Question 6: What are the flight frequency in a day?
We will now investigate the period of the flights. We only consider the estimated time (i.e.: scheduled time).

## Mini-conclusion
There exists a period for the scheduled flights. We can take an average for flights that arrive at a specific hour (i.e.: find the average of flight count that arrives / departs at 1pm).

With this in mind, we can estimate flight schedule of a day even when the data is missing.



# References
1. https://www.hongkongairport.com/iwov-resources/misc/opendata/Flight_Information_DataSpec_en.pdf
2. https://github.com/ip2location/ip2location-iata-icao
3. https://stackoverflow.com/questions/74399077/python-display-loading-animation-while-preforming-a-long-task
4. https://pythonalgos.com/2021/12/26/send-api-requests-asynchronously-in-python/
5. https://stackoverflow.com/questions/47518874/how-do-i-run-python-asyncio-code-in-a-jupyter-notebook
6. https://github.com/ip2location/ip2location-iata-icao/blob/master/iata-icao.csv
7. https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/blob/master/all/all.csv
8. https://stackoverflow.com/questions/22684730/heat-world-map-with-matplotlib
9. https://stackoverflow.com/questions/72580901/how-to-add-a-legend-to-cartopy-plot
10. https://en.wikipedia.org/wiki/Haversine_formula