# ENGG1003 Project

## Academic Honesty
I declare that the lab work here submitted is original
except for source material explicitly acknowledged,
and that the same or closely related material has not been
previously submitted for another course.
I also acknowledge that I am aware of University policy and
regulations on honesty in academic work, and of the disciplinary
guidelines and procedures applicable to breaches of such
policy and regulations, as contained in the website.

University Guideline on Academic Honesty:
https://www.cuhk.edu.hk/policy/academichonesty/

Student Name : Cheung Yik Fung

Student ID : 1155211679

Class/Section : ENGG1003EC

Date : 12-12-2023

## Project description
After the pandemic, what happens to the Hong Kong Airport? How is the operation right now? Through this project, we will analyse the flight information of the Hong Kong Airport in real-time, to resolve the following problems:
1. What is the average / minimum / maximum / s.d. delay of the flights for the last 90 days?
2. What are the common destinations / origins of the flights?
3. Are longer routes generally have a longer delay?
4. Will flights arrived / departed at night have a longer delay?
5. Do longer routes have generally less flights?
6. What are the flight frequency in a day?

## Work Description
Please click the code blocks in order to use this smoothly. There is a `Fetcher` class for data fetching with `static` and `dynamic` mode (we will only use static mode in this project). `FlightIdentifier` and `Flight` are the classes to store a single flight information. `FlightAnalyser` is the base class for basic operations of data retrieval. `QuestionX` class indicates that the problem we want to investigate in. Please call the following if you want to run the questions individually for your personal interest:
```py
loop = asyncio.get_event_loop()
fa = QuestionX(loop, mode="static")
fa.solver(...) # put some parameters here if needed
fa.solverX(...) # if there are multiple solvers in a class, use this
```

I also put this project to Github and make it public (I guess I uploaded it after deadline of the project so no academic dishonesty). The link is here: 