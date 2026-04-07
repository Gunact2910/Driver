CC = gcc
CFLAGS = -Wall -Wextra -O2
TARGET = student_mgmt
SRCS = main.c auth.c student.c sha256.c string_utils.c
OBJS = $(SRCS:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

run: $(TARGET)
	./$(TARGET)

webui:
	python3 student_web.py

app:
	python3 student_app.py

kbdash:
	python3 keyboard_dashboard.py

kbdash-app:
	python3 keyboard_dashboard_app.py

.PHONY: all clean run webui app kbdash kbdash-app
