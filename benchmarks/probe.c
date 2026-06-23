#include <stdio.h>
#include <math.h>
#include <time.h>
double heavy_logic(double posx, double posy, double px, double py) {
    double acc = 0.0;
    for (int s = 0; s < 16; s++) {
        double t = s / 16.0;
        double sx = posx + (px - posx) * t;
        double sy = posy + (py - posy) * t;
        acc += sin(sx * 0.1) * cos(sy * 0.1);
    }
    double grid[8][8];
    for (int gy=0; gy<8; gy++) for (int gx=0; gx<8; gx++) grid[gy][gx] = fabs((double)gx-(double)gy)+acc*0.0001;
    double best=1e9;
    for (int gy=0; gy<8; gy++) for (int gx=0; gx<8; gx++) if (grid[gy][gx]<best) best=grid[gy][gx];
    return acc+best;
}
int main(){
    double sum=0;
    int N=2000000;
    clock_t start=clock();
    for(int i=0;i<N;i++) sum += heavy_logic(i*0.001, i*0.002, 0,0);
    double el=(double)(clock()-start)/CLOCKS_PER_SEC;
    printf("sum=%f time=%f calls=%d  ns/call=%f\n", sum, el, N, el*1e9/N);
    return 0;
}
