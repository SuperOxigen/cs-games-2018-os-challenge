/*
 * CS Games 2018 - Operating System Challenge
 */

#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

void write_uint16_to_packet(char * packet_buffer, int offset, uint16_t value) {
    if (!packet_buffer) return;
    /* Convert the integer byte representation to network order */
    value = htons(value);
    memcpy(&packet_buffer[offset], &value, 2);
}

uint16_t read_uint16_from_packet(char * packet_buffer, int offset) {
    uint16_t value;
    if (!packet_buffer) return 0;
    memcpy(&value, &packet_buffer[offset], 2);
    return ntohs(value);
}


int main(int argc, char ** argv) {
    int port;
    /* Add your variables here. */

    if (argc < 2 || sscanf(argv[1], "%d", &port) != 1) {
        fprintf(stderr, "Program requires a port number as the first argument\n");
        exit(EXIT_FAILURE);
    }

    if (port <= 1023 || port > 65535) {
        fprintf(stderr, "Port number must be greater than or equal to 1024 "
                        "and less than or equal to 65535\n");
    }

}
