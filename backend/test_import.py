import traceback
import sys

try:
    import enhanced_main
except Exception as e:
    with open("err_trace.txt", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    print("Error saved to err_trace.txt")
except BaseException as e:
    with open("err_trace.txt", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    print("Error saved to err_trace.txt")
