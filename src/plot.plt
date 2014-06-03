set terminal pdf
set output 'test.pdf'
set xlabel 'Delay (ms)'
set xrange [5:65]
set xtics 5,5,65
set ylabel 'Bandwidth (Mbps)'
set yrange [0:100]
set ytics 0,5,100
set grid

plot 'test.dat' using 1:($3/1000) every ::0::4 t '100 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::5::9 t '90 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::10::14 t '80 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::15::19 t '70 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::20::24 t '60 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::25::29 t '50 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::30::34 t '40 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::35::39 t '30 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::40::44 t '20 Mbps' with linespoints, \
     'test.dat' using 1:($3/1000) every ::45::49 t '10 Mbps' with linespoints

