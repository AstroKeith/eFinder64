<!DOCTYPE html>
<html>
<head>
	<title>Efinder</title>
	
</head>


<?php

$image = '/home/efinder/Solver/images/image.jpg';
$imageData = base64_encode(file_get_contents($image));
echo '<img src="data:image/jpg;base64,'.$imageData.'">';
?>

