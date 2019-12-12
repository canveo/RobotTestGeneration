#!/bin/zsh

# Change the ROS_MASTER_URI to allow multiple version of ROS to run at the same time
ROS_MASTER_URI=http://localhost:11312

# Source the ros workspace
source devel/setup.zsh

# Used to save the port number
port=25002

# Create a temporary unity folder
mkdir -p ./tmp_dir/
cp -r ../Unity/Build ./tmp_dir/Build
mv ./tmp_dir/Build ./tmp_dir/Build${port}

# Go into the directory
cd ./tmp_dir/Build${port}

# Get current directory
current_dir="$PWD"

# Change the port number inside the new build
sed -i -e 's/(25001)/('$port')/g' ./config.txt

# Variables we can change
searchtype="maxvel"
score="random"
savename="initial"

trajectorylength=5
beamwidth=5
nodes=250
resolution=4
seed=10
totaltime=3600
simulationtime=45

initial_MIT_seed10_length5_nodes250_res4_beamwidth5_totaltime3600_simtime45_searchtype_maxvel_scoretype_random

results_folder='/home/autosoftlab/Desktop/RobotTestGeneration/TestGeneration/FinalResults/initial_run_flown'

for minsnap in 1
do

	# Get the folder
	folder=${results_folder}/${savename}_MIT_seed${seed}_length${trajectorylength}_nodes${nodes}_res${resolution}_beamwidth${beamwidth}_totaltime${totaltime}_simtime${simulationtime}_searchtype_${searchtype}_scoretype_${score}

	# Get the total number of tests to run
	mapcounter=1
	totaltests=$(ls $folder/maps | wc -l)

	echo "--------------------------------------------------------"
	echo "Processing: $folder"
	echo "Total tests found: $totaltests"
	echo "--------------------------------------------------------"

	while [ $mapcounter -le $totaltests ]
	do
		echo "Processing: $folder/maps/map$mapcounter"
		echo " "

		# If it is in min snap mode
		if [ $minsnap -ne 0 ]
		then
			declare -a speeds=(-1)
		# Otherwise use all speeds
		else
			declare -a speeds=(-1 -2 2 5 10)
		fi

		for speed in "${speeds[@]}"
		do

			# Get the current test
			cp $folder/maps/map$mapcounter/test.txt $PWD/test.txt

			# Run the simulator
			./WorldEngine.x86_64 &

			# Get the PID so that I can kill it later
			unity_PID=$!

			# Wait 30 seconds for unity to start
			sleep 20

			# Launch the ros file
			roslaunch flightcontroller fly.launch port:="$port" test_location:="$current_dir" save_location:="$current_dir" speed:="$speed" minsnap:="$minsnap" &

			# Get the PID so that I can kill it later
			roslaunch_PID=$!

			# Each test is given ${simulationtime} seconds
			sleep ${simulationtime}

			# Kill the code
			kill -INT $unity_PID
			kill -INT $roslaunch_PID

			# Remove the temporary test
			rm test.txt
			
			# Save the test to the appropriate file
			mv performance.txt $folder/maps/map$mapcounter/performance_speed$speed\_minsnap$minsnap.txt
			mv attitude_thrust_log.txt $folder/maps/map$mapcounter/attitude_thrust_log_speed$speed\_minsnap$minsnap.txt
			mv velocity_log.txt $folder/maps/map$mapcounter/velocity_log_speed$speed\_minsnap$minsnap.txt
			mv angular_rate_log.txt $folder/maps/map$mapcounter/angular_rate_log_speed$speed\_minsnap$minsnap.txt

			# If it is in min snap mode
			if [ $minsnap -ne 0 ]
			then
				mv all_minsnap$minsnap.png $folder/maps/map$mapcounter/all_minsnap$minsnap\_speed$speed.png
				mv sidexz_minsnap$minsnap.png $folder/maps/map$mapcounter/sidexz_minsnap$minsnap\_speed$speed.png
				mv sideyz_minsnap$minsnap.png $folder/maps/map$mapcounter/sideyz_minsnap$minsnap\_speed$speed.png
				mv top_minsnap$minsnap.png $folder/maps/map$mapcounter/top_minsnap$minsnap\_speed$speed.png
			fi

			# Allow 5 seconds for clean up
			sleep 5
		
		# End speed
		done

		# Increment the mapcounter
		((mapcounter++))
	done
done

echo "Done"

# Go back to the original dir
cd $current_dir
cd ..

# Delete the temp files
rm -r ./Build$port

echo Completed Script