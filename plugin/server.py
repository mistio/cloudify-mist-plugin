from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
from mistclient import MistClient
import uuid
from time import sleep

@operation
def create(**kwargs):
	client = MistClient(email=kwargs['username'], password=kwargs['password'])
	ctx.instance.runtime_properties['mist_client']=client
	backend = client.backends(id=kwargs['backend_id'])[0]
	if "key" in kwargs:
		key=client.keys(search=kwargs["key"])
		if len(key):
			key=key[0]
		else:
			raise NonRecoverableError("key not found")
	else:
		keys = client.keys()
		for k in keys:
			if k.is_default:
				ctx.logger.info('Using default key ')
				key=k 
		if not key:
			ctx.logger.info('No key found. Trying to generate one and add one.')
			private = client.generate_key()
			client.add_key(key_name=kwargs["name"], private=private)
			key=client.keys(search=kwargs["name"])[0]
	uid=uuid.uuid4().hex	
	ctx.instance.runtime_properties['name']=kwargs["name"]+uid	
	job_id=backend.create_machine(async=True,name=kwargs["name"]+uid, key=key, image_id=kwargs["image_id"], location_id=kwargs["location_id"], size_id=kwargs["size_id"])
	job_id=job_id.json()["job_id"]
	job=client.get_job(job_id)
	while True:
		if job["summary"]["probe"]["success"]:
			break
		if job["summary"]["create"]["error"] or job["summary"]["probe"]["error"]:
			ctx.logger.error('Error on machine creation ')
			raise NonRecoverableError("Not able to create machine")
		sleep(10)
		job=client.get_job(job_id)	
	backend.update_machines()
	machine= backend.machines(search=kwargs["name"]+uid)[0]
	ctx.instance.runtime_properties['machine']=machine
	ctx.instance.runtime_properties['backend']=backend
	ctx.instance.runtime_properties['name']=machine.info["name"]
	ctx.instance.runtime_properties['ip']=machine.info["public_ips"][0]
	ctx.instance.runtime_properties['networks']={"default":machine.info["public_ips"][0]}
	ctx.logger.info('Machine created')


@operation
def start(**kwargs):
	ctx.instance.runtime_properties['machine'].start()
	ctx.logger.info('Machine started')

@operation
def stop(**kwargs):
	ctx.instance.runtime_properties['machine'].stop()
	ctx.logger.info('Machine stopped')

@operation
def delete(**kwargs):
	ctx.instance.runtime_properties['machine'].destroy()
	ctx.logger.info('Machine destroyed')


	

