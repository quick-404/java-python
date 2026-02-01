package com.example.ast;

public class Demo {

    private String name;
    private int count;

    public Demo(String name, int count) {
        this.name = name;
        this.count = count;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public int add(int a, int b) {
        return a + b;
    }

    public void printInfo() {
        System.out.println("Name: " + name + ", Count: " + count);
    }
}
