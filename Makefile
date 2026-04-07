CC = gcc
CFLAGS = -Wall -Wextra -O2
TARGET = student_mgmt
SRCS = main.c auth.c student.c sha256.c string_utils.c
OBJS = $(SRCS:.c=.o)
KB_NORMALIZE_LIB = libkbnormalize.so

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

$(KB_NORMALIZE_LIB): driver/string_utils_bridge.c driver/string_utils_shared.h
	$(CC) -Wall -Wextra -O2 -shared -fPIC -o $@ driver/string_utils_bridge.c

clean:
	rm -f $(OBJS) $(TARGET) $(KB_NORMALIZE_LIB)

run: $(TARGET)
	./$(TARGET)

webui:
	python3 student_web.py

app: $(KB_NORMALIZE_LIB)
	python3 student_app.py

kbnormalize:
	$(MAKE) $(KB_NORMALIZE_LIB)

kbdash:
	python3 keyboard_dashboard.py

kbdash-app:
	python3 keyboard_dashboard_app.py

.PHONY: all clean run webui app kbdash kbdash-app kbnormalize
