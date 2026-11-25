package com.smartdoor.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class SmartDoorApplication {
    public static void main(String[] args) {
        SpringApplication.run(SmartDoorApplication.class, args);
    }
}
