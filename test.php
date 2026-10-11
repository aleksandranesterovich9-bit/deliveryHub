<?php

$numbers = [4, 7, 2, 9, 6, 1];
$max = 0;

foreach ($numbers as $num) {
    if ($num % 2 == 0 && $num > $max) {
        $max = $num;
    }
}

echo $max;