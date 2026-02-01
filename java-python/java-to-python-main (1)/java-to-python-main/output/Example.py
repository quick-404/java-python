class Example:
    count = 5
    name = "example"
    def __init__(self):
        self.count = 1
        self.name = "default"
    def __init__(self, count, name):
        self.count = count
        self.name = name
    def sayHello(self):
        print("Hello, " + self.name)
    def printNumbers(self):
        # For loop converted to while loop
        i = 0
        while i < self.count:
            pass
        i += 1
                    print("i = " + i)
    def countdown(self):
        int x = count
        while x > 0:
                    print("x = " + x)
                    x -= 1
    def doSomething(self):
        int y = 0
        # Do-while loop converted to while loop
        while True:
                    print("doing: " + y)
                    y += 1
            if not (y < 3):
                break
    def checkValue(self, v):
        if v > 10:
                    print("Large")
        else:
                    print("Small or equal")
        try:
                    if v < 0:
                    print("Value ok")
        except IllegalArgumentException as ex:
                    print("Caught: " + ex.args)
    def main(self, args):
        Example ex1 = Example()
        ex1.sayHello()
        Example ex2 = Example(3, "Alice")
        ex2.printNumbers()
        ex2.countdown()
        ex2.doSomething()
        ex2.checkValue(5)
        ex2.checkValue(-1)
        self.list = []
        self.list.add("A")
        self.list.add("B")