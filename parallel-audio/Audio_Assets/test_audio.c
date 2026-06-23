#define MINIAUDIO_IMPLEMENTATION  
#include "..\miniaudio.h"  
#include <stdio.h>  
int main() {  
    ma_context context;  
    if (ma_context_init(NULL, 0, NULL, &context) != MA_SUCCESS) {  
        printf("Failed to init audio.\n");  
        return -1;  
    }  
    printf("Successfully initialized audio subsystem!\n");  
    ma_context_uninit(&context);  
    return 0;  
} 
