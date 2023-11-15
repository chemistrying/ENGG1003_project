from airport import *
import asyncio
import time

async def loading_animation():
    delay = 0.5
    i = 0
    fetching = ["\rFetching.  ", "\rFetching.. ", "\rFetching..."]
    while True:
        print(fetching[i % len(fetching)], end="")
        i += 1
        await asyncio.sleep(delay)

async def analyse_process(loop):
    # The question we are handling
    fa = Question1(loop)

    # Input section
    interval = 90

    start_time = time.time()

    # await fa.solver1(interval=interval, arrival=True)
    # await fa.solver1(interval=interval, arrival=False)
    # await fa.solver2(interval=interval, arrival=True)
    await fa.solver3(interval=interval, arrival=True)

    end_time = time.time()
    print(f"\r--- {round(end_time - start_time, 2)}s elapsed ---")

    await fa.finish()

async def fetching_process(loop, loading_task):
    # main code starts here
    await analyse_process(loop)
    # main code ends here

    try:
        loading_task.cancel()
    except:
        return

async def main(loop):
    loading_task = asyncio.create_task(loading_animation())
    fetching_task = asyncio.create_task(fetching_process(loop, loading_task))
    
    await fetching_task
    try:
        await loading_task
    except:
        pass

    import matplotlib.pyplot as plt
    plt.show()

loop = asyncio.get_event_loop()
main_task = loop.create_task(main(loop))
loop.run_until_complete(main_task)

# Cleansing the console
print("\r")