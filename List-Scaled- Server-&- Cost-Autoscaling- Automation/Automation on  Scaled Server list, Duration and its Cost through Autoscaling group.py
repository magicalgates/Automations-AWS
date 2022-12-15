from cProfile import run
import boto3
from datetime import datetime
from dateutil import tz
import csv

#Auto-detect zones:
from_zone = tz.tzutc()
to_zone = tz.tzlocal()

ec2 = boto3.client('ec2')
asg = boto3.client('autoscaling')
cloudtrail = boto3.client('cloudtrail')

Fromdate = input("Enter From_date (YYYY-MM-DD): ") #input by user '2022-09-18'
a = datetime.strptime(Fromdate, "%Y-%m-%d")
# print(type(a))

Todate = input("Enter To_date (YYYY-MM-DD): ") #input by user '2022-10-18'
b = datetime.strptime(Todate, "%Y-%m-%d")
# print(type(b))

InstanceTypeCost = float(input("Enter the Cost of Instancetype which is used by specified Autoscalinggroup: "))

CSVfilename = input("Enter the Name of CSV file: ")

response = asg.describe_scaling_activities(
    ActivityIds=[],
    AutoScalingGroupName='NDS-CYNC-PROD-NGINX-ASG', #Specify the Autoscalinggroupname
    IncludeDeletedGroups=True,
    MaxRecords=1
)
# print(response)

asg_activities = response['Activities']

while 'NextToken' in response:
    response = asg.describe_scaling_activities(
        ActivityIds=[],
        AutoScalingGroupName= 'NDS-CYNC-PROD-NGINX-ASG', #Specify the Autoscalinggroupname
        IncludeDeletedGroups=True,
        MaxRecords= 1, 
        NextToken=response['NextToken'])
    asg_activities.extend(response['Activities'])

format_str = '%Y-%m-%d %H:%M:%S'

with open(CSVfilename +'.csv', 'w') as csvfile: 
    fields = ['InstanceId', 'LaunchTime', 'TerminationTime', 'RunTime(Days Hr:Min:Sec)', 'RunTime(Hr)', 'InstanceCost($)'] 
    writer = csv.writer(csvfile)
    writer.writerow(fields) 
    for i in asg_activities:
        activity = i['ActivityId']
        description = i['Description']
        # print(description)
        # print(activity)
        if "Terminating" in description:
            # Get instance termination date and time in UTC
            terminationtimeinUTC = i['EndTime'] 
            # Converting instance termination date and time to IST
            terminationtimeinUTC = terminationtimeinUTC.replace(tzinfo=from_zone)
            terminationtimeinIST = terminationtimeinUTC.astimezone(to_zone)
            #Used to compare the date and time
            end = terminationtimeinIST.strftime(format_str)
            end_date = datetime.strptime(end, format_str)
            if (end_date >= a) and (end_date <= b):
                #Slicing only the instance Id from the description and passing that Id to cloudtrail event
                x=slice(26, 45) 
                x1 = description[x]
                #Using paginator to get instance details from the cloudtrail
                paginator = cloudtrail.get_paginator('lookup_events')
                #Applying Filters
                page_iterator = paginator.paginate(LookupAttributes=[{'AttributeKey': 'ResourceName', 'AttributeValue': x1}])
                for page in page_iterator:
                    for event in page['Events']:
                        if event["EventName"] == "RunInstances":
                            #Get instance launch time from cloudtrail in IST 
                            launchtimeinIST = event['EventTime']
                            #Used to compare the date and time
                            start = launchtimeinIST.strftime(format_str)
                            start_date = datetime.strptime(start, format_str)
                            #Got the duration in seconds 
                            duration = ((end_date) - (start_date)).total_seconds()
                            #Converting got duration to hours 
                            durationinhours = float(duration/3600)
                            #This has the Runtime of instance in days Hr:Min:sec format
                            runtime = (terminationtimeinIST - launchtimeinIST)
                            # Calculating the cost of each instance in ASG activities
                            costofinstance = durationinhours*InstanceTypeCost #hourly cost of this Asg instancetype
                            temp = [x1, launchtimeinIST, terminationtimeinIST, runtime, durationinhours, costofinstance]
                            writer.writerows([temp])
                            # print(x1) #print instance id
                            # print(launchtimeinIST) #print launch time of instance
                            # print(terminationtimeinIST) #print termination time of instance
            elif "Terminating" not in description:
                continue
csvfile.close()
                        