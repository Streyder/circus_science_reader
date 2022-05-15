#include <ArduinoBLE.h>
#include <Arduino_LSM9DS1.h>

#define RED_PIN 22     
#define BLUE_PIN 24     
#define GREEN_PIN 23


// Set these values as required
#define DEBUG false
#define VALUES_PER_DATASET 6
#define FLOATS_PER_DATASET 10
#define DATA_ARRAY_SIZE FLOATS_PER_DATASET * VALUES_PER_DATASET * 4


// These UUIDs have been randomly generated. - they must match between the Central and Peripheral devices
// Any changes you make here must be suitably made in the Python program as well
BLEService nanoService("fc0a2500-af4b-4c14-b795-a49e9f7e6b84"); // BLE Service
BLECharacteristic dataCharacteristic("fc0a2501-af4b-4c14-b795-a49e9f7e6b84", BLEWriteWithoutResponse | BLENotify, DATA_ARRAY_SIZE, true);


byte blue_led_state = HIGH;
float gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z;
int data_index = 0;
float data[FLOATS_PER_DATASET * VALUES_PER_DATASET];


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
    nanoService.addCharacteristic(dataCharacteristic);

    // add service
    BLE.addService(nanoService);

    // set the initial value for the characeristic:
    dataCharacteristic.writeValue(data, DATA_ARRAY_SIZE);

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
            data_index = 0;
            for (int i = 0; i<FLOATS_PER_DATASET; i++) {
              if (!IMU.accelerationAvailable() || !IMU.gyroscopeAvailable()){
                i = i - 1;
                continue;
              }
              
              IMU.readGyroscope(gyro_x, gyro_y, gyro_z);
              IMU.readAcceleration(accel_x, accel_y, accel_z);
  
              // Build our data
              data[data_index] = gyro_x;
              data[data_index + 1] = gyro_y;
              data[data_index + 2] = gyro_z;

              data[data_index + 3] = accel_x;
              data[data_index + 4] = accel_y;
              data[data_index + 5] = accel_z;

              data_index = data_index + 6;
            }
            
            dataCharacteristic.writeValue(data, DATA_ARRAY_SIZE);

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
