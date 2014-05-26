set terminal png giant size 1024,768
set output 'test.png'
set xlabel 'Delay (ms)'
set xrange [-1:51]
set xtics -10,10,60
set ylabel 'Bandwidth (Mbps)'
set yrange [0:100000]
set ytics 0,5000,100000
set grid

plot 'test.dat' using 1:3 every ::0::5 t '100 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::6::11 t '90 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::12::17 t '80 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::18::23 t '70 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::24::29 t '60 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::30::35 t '50 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::36::41 t '40 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::42::47 t '30 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::48::53 t '20 Mbps' with linespoints, \
     'test.dat' using 1:3 every ::54::59 t '10 Mbps' with linespoints

