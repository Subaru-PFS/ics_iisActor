/*
 * adcreadone(chan(1-8))
 *  Created on: 17 Jan 2018
 *
 *      compile with "gcc ABE_ADCPi.c adc.c -o adc"
 *      run with "./adc(chan)"
 */

#include <stdio.h>
#include <stdint.h>
#include <time.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include "ABE_ADCPi.h"

int main(int argc, char **argv){
    if (argc < 2) {
        printf("USAGE: adc chan(1-8)\n");
        return (-1);
    }
    int chan = atoi(argv[1]);
    
    if(chan < 1 || chan > 8){
        printf("\nThere is no channel %d",chan);
        return (-1);
    }
    setvbuf (stdout, NULL, _IONBF, 0); // needed to print to the command line

    int addr = (chan <5 ? 0x68 : 0x69);
    int subchan = ((chan -1)%4) + 1 ;
    /* printf("\nreading from channel %d address %x, subchan %d\n",chan,addr,subchan); */
    double volts = read_voltage(addr,subchan,16,1,1);
    printf("%6.4f\n",volts);
    return (0);
}
