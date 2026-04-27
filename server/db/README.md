So you’re in the repository?
If you want to run everything, please do

cp .env.example .env

This is because some of the services you’ll be running use environmental variables, most specifically, the InfluxDB token which remains private to each user. 

Then do

Docker compose up -d –build 

And then generate token for InfluxDB with

docker exec influxdb3-core influxdb3 create token --admin

Please copy and paste what you get onto your .env file
Copy your token, it should start with something like apiv3_…
Vim .env
Paste onto the line for the token, so it is like INFLUXDB_TOKEN=apiv3…

Open up InfluxDB 3 Explorer and Connect to the Database
Go to Configure
Server name: daqDB
URL: influxdb3-core:8181
Token: <what was copied and pasted before for INFLUXDB_TOKEN>

To View Published Data from MQTT in InfluxDB 3 Explorer
Go to Query Data > Data Explorer
Select daqDB
Tables should show up with corresponding data
