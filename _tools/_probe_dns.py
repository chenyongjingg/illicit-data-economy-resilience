import socket, sys, os
# ★ C-416: host and port are read from the ENVIRONMENT. They used to be literals
# here. This file is published (it is in the repo whitelist), and a host baked into a
# source file is a host that ships with the code -- the same rule the PORT and PASS
# lines of rsc.py follow.
h = os.environ["CIS_HOST"]
p = int(os.environ["CIS_PORT"])
print("argv0:", sys.argv[0], "cwd:", os.getcwd(), "prefix:", sys.prefix)
try:
    print("OK", socket.getaddrinfo(h, p, socket.AF_INET, socket.SOCK_STREAM)[0][4])
except Exception as e:
    print("FAIL", type(e).__name__, e)
