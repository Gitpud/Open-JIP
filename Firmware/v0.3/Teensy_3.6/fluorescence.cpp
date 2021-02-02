/* <Open-JIP (v0.3) Teensy 3.6 Script. Controls "Open-JIP" chlorophyll fluorometer v0.3>
     Copyright (C) <2020>  <Harvey Bates>

     This program is free software: you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation, either version 3 of the License, or
     (at your option) any later version.
     
     This program is distributed in the hope that it will be useful,
     but WITHOUT ANY WARRANTY; without even the implied warranty of
     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
     GNU General Public License for more details.
     
     You should have received a copy of the GNU General Public License
     along with this program.  If not, see <https://www.gnu.org/licenses/>
     
     For more information contact: harvey.bates@student.uts.edu.au or see
     https://github.com/HarveyBates/Open-JIP 
*/ 

#include "fluorescence.h"

Fluorescence::Fluorescence(){
  set_reference_voltage(refVoltage); // Only applicable with a Teensy 3.6 (disable if using other microcontroller)
}

void Fluorescence::set_reference_voltage(float voltage){
  // Sets and initalises the required reference voltage for measurments
  if(voltage == 3.3){
    analogReference(DEFAULT); // Set to 3.3 V
  }
  else if(voltage == 1.1){
    analogReference(INTERNAL1V1); // Set to 1.1 V
  }
  else{
    analogReference(DEFAULT); // Set to default (3.3 V) if unknown value is found
  }
  analogRead(readPin); // Initalise reference voltage
}

void Fluorescence::measure_j_step(Actinic actinic){
  /* Measures up to the J-Step (2 ms) and prints the values in the serial output*/
  set_reference_voltage(refVoltage);
  
  actinic.on();
  long timer = micros();

  /* Read the values */
  for(unsigned int i = 0; i < sizeof(microReadJ) / sizeof(int); i++){
    microReadJ[i] = analogRead(readPin);
    microTimeJ[i] = micros() - timer;
  }

  actinic.off();

  /* Convert and print out the values */
  for(unsigned int i = 0; i < sizeof(microReadJ) / sizeof(int); i++){
    jTime[i] = microTimeJ[i] / 1000.0; // Convert to ms
    jValues[i] = (microReadJ[i] * refVoltage) / 4096.0; // Convert bits to V
    Serial.print(jTime[i], 3); 
    Serial.print("\t");
    Serial.println(jValues[i], 4);
    delay(5);
  }
}


void Fluorescence::wave(Actinic actinic){
  set_reference_voltage(refVoltage); 
  int wavePos = 0; // Keeps track of position in wave acquisition array
  for(unsigned int i = 0; i < numWaves; i++){
    
    actinic.on();
    long timer = micros();
      
    for(unsigned int x = 0; x < waveAqu; x++){
      waveRead[wavePos] = analogRead(readPin);
      waveTime[wavePos] = micros() - timer;
      wavePos++;
    }
    
    actinic.off();
    delay(waveInterval); // Delay for specified interval
  }

  // Prints out the data
  for(unsigned int i = 0; i < waveLength; i++){
    Serial.print(waveTime[i] / 1000.0, 3); 
    Serial.print("\t");
    Serial.println((waveRead[i] * refVoltage) / 4096.0, 4);
  }
}

void Fluorescence::measure_fluorescence(Actinic actinic) {
  actinic.on();

  long timer = micros(); // Start timer 

  // Read microsecond fluorescence values and corresponding timestamps
  for (unsigned int i = 0; i < sizeof(microRead) / sizeof(int); i++) 
  {
    microRead[i] = analogRead(readPin);
    microTime[i] = micros() - timer;
  }

  // Read millisecond fluorescence values and corresponding timestamps
  for (unsigned int i = 0; i < sizeof(milliRead) / sizeof(int); i++) 
  {
    milliRead[i] = analogRead(readPin);
    milliTime[i] = micros() - timer;
    delay(1);
  }
  
  actinic.off(); // Turn off actinic LED
  delay(10);

  // Convert micros() to milliseconds (ms) for microsecond values and convert bits to voltage
  for (unsigned int i = 0; i < sizeof(microRead) / sizeof(int); i++)
  {
   float milliReal = microTime[i]/1000; // Convert micros() to ms
   // Find fm value, we do this here while data are still ints
   if (microRead[i] > fm){
    fm = microRead[i];
   }
   fluorescenceValues[i] = (microRead[i] * refVoltage) / 4096; // Convert to volts and append to final array
   timeStamps[i] = milliReal; // Append time to final array
   Serial.print(milliReal, 3); 
   Serial.print("\t");
   Serial.println((microRead[i] * refVoltage) / 4096, 4);
   delay(1);
  }

  // Convert micros() to milliseconds for millsecond values and convert bits to voltage
  for (unsigned int i = 0; i < sizeof(milliRead) / sizeof(int); i++) 
  {
   float milliReal = milliTime[i]/1000; // Convert micros() to ms
   // Find fm value if not in microsecond range
   if (milliRead[i] > fm){
    fm = milliRead[i];
   }
   fluorescenceValues[i + microLength] = (milliRead[i] * refVoltage) / 4096; // Convert to V and append
   timeStamps[i + microLength] = milliReal; // Append to timestamps after microRead data
   Serial.print(milliReal, 3); 
   Serial.print("\t");
   Serial.println((milliRead[i] * refVoltage) / 4096, 4);
   delay(1);
  }
}

void Fluorescence::calculate_parameters(){
  float fo = fluorescenceValues[fo_pos]; // Gets the minimum level fluorescence (Fo)
  float fj = 0.0f, fi = 0.0f;
  float  fj_time = 0.0f, fi_time = 0.0f, fm_time = 0.0f;
  bool fj_found = false, fi_found = false;

  // Next loop gets the Fj and Fi values at 2 and 30 ms respsctively 
  for(unsigned int i = 0; i < sizeof(timeStamps) / sizeof(int); i++){
    // Search for timestamp corresponding to 2 ms
    if(!fj_found && int(timeStamps[i]) == 2){
      fj = fluorescenceValues[i];
      fj_time = timeStamps[i];
      fj_found = true;
    }
    else if(!fi_found && int(timeStamps[i]) == 30){
      fi = fluorescenceValues[i];
      fi_time = timeStamps[i];
      fi_found = true;
    }
  }

  float fm_volts = (fm * refVoltage) / 4096.0;
  float fv = fm_volts - fo;
  float fvfm = fv / fm_volts;

  Serial.println();
  Serial.print("Fo: \t");
  Serial.print(fo, 4);
  Serial.print(" V @ ");
  Serial.print(timeStamps[fo_pos], 4);
  Serial.println(" ms");
  Serial.print("Fj: \t");
  Serial.print(fj, 4);
  Serial.println(" V @ " + String(fj_time) + " ms");
  Serial.print("Fi: \t");
  Serial.print(fi, 4);
  Serial.println(" V @ " + String(fi_time) + " ms");
  Serial.print("Fm: \t");
  Serial.print(fm_volts, 4);
  Serial.println(" V @ " + String(fm_time) + " ms");
  Serial.print("Fv: \t");
  Serial.print(fv, 4);
  Serial.println(" V");
  Serial.print("Quantum yield (Fv/Fm): \t");
  Serial.print(fvfm, 3);
  if(fvfm < 0.5){
    Serial.println(" Poor health");
  }
  else if(fvfm >= 0.5 && fvfm < 0.7){
    Serial.println(" Moderately healthy");
  }
  else if(fvfm >= 0.7){
    Serial.println(" Healthy");
  }
}

void Fluorescence::calibrate_fo(Actinic actinic){
  /* Calibrate the fo value of the fluorometer, can be used to ensure the concentration of algae
  is not too high
  */  
  float foread = 0.0f;
  for (int k = 0; k < 5; k++){
    actinic.on();
    delayMicroseconds(20);
    for (int i = 0; i <= 2; i++){
      foread = analogRead(readPin);
      Serial.println((foread/4096) * refVoltage);
    }
    actinic.off();
    Serial.print("Final Fo = ");
    Serial.println((foread/4096) * refVoltage);
    delay(2000);
    }
}

void Fluorescence::calibrate_rise(Actinic actinic){
  // Calibrate the rise time of the flurometer (useful for debugging)
  for (int i = 0; i < 200; i++){
    actinic.on();
    delayMicroseconds(100);
    actinic.off();
    delay(200);
  }
}

void Fluorescence::measure_light(Actinic actinic){
  // Measure light using external 4pi light meter
  actinic.on();
  delay(3000);
  actinic.off();
  delay(20);
}