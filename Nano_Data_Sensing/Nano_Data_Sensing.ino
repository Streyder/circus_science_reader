#include <ArduinoBLE.h>
#include <Arduino_LSM9DS1.h>

#define RED_PIN 22     
#define BLUE_PIN 24     
#define GREEN_PIN 23


// Set these values as required
#define DEBUG false
#define FLOAT_PRECISION 4
#define DATASET_SIZE 10

byte blue_led_state = HIGH;
float gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z;
String dataString = "";
float data[DATASET_SIZE*6];

// These UUIDs have been randomly generated. - they must match between the Central and Peripheral devices
// Any changes you make here must be suitably made in the Python program as well

BLEService nanoService("fc0a2500-af4b-4c14-b795-a49e9f7e6b84"); // BLE Service
BLECharacteristic accelStringCharacteristic("fc0a2501-af4b-4c14-b795-a49e9f7e6b84", BLEWriteWithoutResponse | BLENotify, data, sizeof(data));



void setup() {
    Serial.begin(9600);

    // intitialize the LED Pins as an output
    pinMode(RED_PIN, OUTPUT); // Used to signalize "Waiting for serial to be connected"
    pinMode(BLUE_PIN, OUTPUT); // Used to signalize "Waiting for Bluetooth client to be connected"
    pinMode(GREEN_PIN, OUTPUT); // Used to signalize "Streaming data to client"

    // The onboard RGB LED has an inverse logic - i.e. HIGH turns it off, and LOW turns in ON
    digitalWrite(RED_PIN, LOW);
    digitalWrite(GREEN_PIN, HIGH);
    digitalWrite(BLUE_PIN, HIGH);
    
    if (DEBUG) {;
      while(!Serial);
    }
    
    digitalWrite(RED_PIN, HIGH); // Signalize serial hs connected
    
    // Initialize BLE Service
    if (!BLE.begin()) {
        Serial.println("Starting BLE failed!");
        while (1);
    }

    // set advertised local name and service UUID:
    BLE.setLocalName("Arduino Nano 33 BLE Sense");
    BLE.setAdvertisedService(nanoService);

    // add the characteristic to the service
    nanoService.addCharacteristic(accelStringCharacteristic);

    // add service
    BLE.addService(nanoService);

    // set the initial value for the characeristic:
    accelStringCharacteristic.writeValue("");

    // start advertising
    BLE.advertise();
    delay(100);
    Serial.println("Arduino Nano BLE Peripheral Service Started");

    if (!IMU.begin()) {
    Serial.println("Failed to initialize IMU!");
    while (1);
    }
    
    Serial.print("Gyroscope sample rate = ");
    Serial.print(IMU.gyroscopeSampleRate());
    Serial.println("Hz");

    Serial.print("Accelerometer sample rate = ");
    Serial.print(IMU.accelerationSampleRate());
    Serial.println(" Hz");
    
    digitalWrite(GREEN_PIN, LOW);
}

void loop() {
    // listen for BLE centrals to connect:
    BLEDevice central = BLE.central();

    // if a client is connected:
    if (central) {
        Serial.print("Connected to client: ");
        // print the clients's MAC address:
        Serial.println(central.address());

        digitalWrite(GREEN_PIN, HIGH); // Signalize a client has connected

        
        // while the client is still connected:
        while (central.connected()) {
            dataString = "";
            for (int i = 0; i<DATASET_SIZE; i++) {
              IMU.readGyroscope(gyro_x, gyro_y, gyro_z);
              IMU.readAcceleration(accel_x, accel_y, accel_z);
  
              // Build our data string. ";" delemit the datasets
              dataString += String(gyro_x, FLOAT_PRECISION) + ";";
              dataString += String(gyro_y, FLOAT_PRECISION) + ";";
              dataString += String(gyro_z, FLOAT_PRECISION) + ";";
  
              dataString += String(accel_x, FLOAT_PRECISION) + ";";
              dataString += String(accel_y, FLOAT_PRECISION) + ";";
              dataString += String(accel_z, FLOAT_PRECISION) + ";";
            }
            
            accelStringCharacteristic.writeValue(dataString);

            digitalWrite(BLUE_PIN, blue_led_state);

            if (blue_led_state == HIGH) {
              blue_led_state = LOW;
            } else {
              blue_led_state = HIGH;
            }
        }

        Serial.print(F("Disconnected from central: "));
        Serial.println(central.address());
        digitalWrite(BLUE_PIN, HIGH); // Disable blue because it might be left on from blinking it
        digitalWrite(GREEN_PIN, LOW); // Signalize client has disconnected and we are ready for new connection
    }
}
