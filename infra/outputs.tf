output "elastic_ip" {
  description = "Elastic IP address of the EC2 instance"
  value       = aws_eip.jira_simulator.public_ip
}

output "public_dns" {
  description = "Public DNS hostname of the EC2 instance"
  value       = aws_eip.jira_simulator.public_dns
}

output "ssh_command" {
  description = "SSH command to connect to the EC2 instance"
  value       = "ssh -i ~/.ssh/jira_simulator.pem ec2-user@${aws_eip.jira_simulator.public_ip}"
}

output "ebs_volume_id" {
  description = "ID of the EBS data volume"
  value       = aws_ebs_volume.data.id
}
