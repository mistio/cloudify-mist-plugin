#!/bin/bash

ADVERTISE_IP=`ifconfig eth0 | grep 'inet ' | cut -d: -f2 | awk '{ print $2}'`
POD_NETWORK=10.2.0.0/16
SERVICE_IP_RANGE=10.3.0.0/24
K8S_SERVICE_IP=10.3.0.1
DNS_SERVICE_IP=10.3.0.10
ETCD_ENDPOINTS=http://127.0.0.1:2379
K8S_VER=v1.1.8_coreos.0

# ETCD configuration
mkdir -p /etc/systemd/system/etcd2.service.d
cat << EOF > /etc/systemd/system/etcd2.service.d/40-listen-address.conf
[Service]
Environment=ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379
Environment=ETCD_ADVERTISE_CLIENT_URLS=http://${ADVERTISE_IP}:2379
EOF

systemctl start etcd2
systemctl enable etcd2

# Prepare kubelet of master server
mkdir -p /etc/kubernetes/manifests
mkdir -p /srv/kubernetes/manifests

/bin/openssl genrsa -out /etc/kubernetes/kube-serviceaccount.key 2048 2>/dev/null
# Configure flannel
mkdir -p /etc/flannel

cat << EOF > /etc/flannel/options.env
FLANNELD_IFACE=${ADVERTISE_IP}
FLANNELD_ETCD_ENDPOINTS=${ETCD_ENDPOINTS}
EOF

mkdir -p /etc/systemd/system/flanneld.service.d
cat << EOF > /etc/systemd/system/flanneld.service.d/40-ExecStartPre-symlink.conf
[Service]
ExecStartPre=/usr/bin/ln -sf /etc/flannel/options.env /run/flannel/options.env
EOF

# Configure docker

mkdir -p /etc/systemd/system/docker.service.d
cat << EOF > /etc/systemd/system/docker.service.d/40-flannel.conf
[Unit]
Requires=flanneld.service
After=flanneld.service
EOF

# Configure kubelet
cat << EOF > /etc/systemd/system/kubelet.service
[Service]
ExecStartPre=/usr/bin/mkdir -p /etc/kubernetes/manifests

Environment=KUBELET_VERSION=${K8S_VER}
ExecStart=/usr/lib/coreos/kubelet-wrapper \
  --api-servers=http://127.0.0.1:8080 \
  --register-node=false \
  --allow-privileged=true \
  --config=/etc/kubernetes/manifests \
  --hostname-override=${ADVERTISE_IP} \
  --cluster-dns=${DNS_SERVICE_IP} \
  --cluster-domain=cluster.local
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF

# Configure kube-apiserver
cat << EOF > /etc/kubernetes/manifests/kube-apiserver.yaml
apiVersion: v1
kind: Pod
metadata:
  name: kube-apiserver
  namespace: kube-system
spec:
  hostNetwork: true
  containers:
  - name: kube-apiserver
    image: quay.io/coreos/hyperkube:v1.1.8_coreos.0
    command:
    - /hyperkube
    - apiserver
    - --bind-address=0.0.0.0
    - --etcd-servers=${ETCD_ENDPOINTS}
    - --allow-privileged=true
    - --insecure-bind-address=0.0.0.0
    - --insecure-port=8080
    - --service-cluster-ip-range=${SERVICE_IP_RANGE}
    - --secure-port=443
    - --advertise-address=${ADVERTISE_IP}
    - --service-account-lookup=false
    ports:
    - containerPort: 443
      hostPort: 443
      name: https
    - containerPort: 8080
      hostPort: 8080
      name: local
EOF

# Configure kube-proxy
cat << EOF > /etc/kubernetes/manifests/kube-proxy.yaml
apiVersion: v1
kind: Pod
metadata:
  name: kube-proxy
  namespace: kube-system
spec:
  hostNetwork: true
  containers:
  - name: kube-proxy
    image: quay.io/coreos/hyperkube:v1.1.8_coreos.0
    command:
    - /hyperkube
    - proxy
    - --master=http://127.0.0.1:8080
    - --proxy-mode=iptables
    securityContext:
      privileged: true
EOF

# Configure kube-podmaster
cat << EOF > /etc/kubernetes/manifests/kube-podmaster.yaml
apiVersion: v1
kind: Pod
metadata:
  name: kube-podmaster
  namespace: kube-system
spec:
  hostNetwork: true
  containers:
  - name: scheduler-elector
    image: gcr.io/google_containers/podmaster:1.1
    command:
    - /podmaster
    - --etcd-servers=${ETCD_ENDPOINTS}
    - --key=scheduler
    - --whoami=${ADVERTISE_IP}
    - --source-file=/src/manifests/kube-scheduler.yaml
    - --dest-file=/dst/manifests/kube-scheduler.yaml
    volumeMounts:
    - mountPath: /src/manifests
      name: manifest-src
      readOnly: true
    - mountPath: /dst/manifests
      name: manifest-dst
  - name: controller-manager-elector
    image: gcr.io/google_containers/podmaster:1.1
    command:
    - /podmaster
    - --etcd-servers=${ETCD_ENDPOINTS}
    - --key=controller
    - --whoami=${ADVERTISE_IP}
    - --source-file=/src/manifests/kube-controller-manager.yaml
    - --dest-file=/dst/manifests/kube-controller-manager.yaml
    terminationMessagePath: /dev/termination-log
    volumeMounts:
    - mountPath: /src/manifests
      name: manifest-src
      readOnly: true
    - mountPath: /dst/manifests
      name: manifest-dst
  volumes:
  - hostPath:
      path: /srv/kubernetes/manifests
    name: manifest-src
  - hostPath:
      path: /etc/kubernetes/manifests
    name: manifest-dst
EOF

# Configure kube-controller-manager
cat << EOF > /srv/kubernetes/manifests/kube-controller-manager.yaml
apiVersion: v1
kind: Pod
metadata:
  name: kube-controller-manager
  namespace: kube-system
spec:
  hostNetwork: true
  containers:
  - name: kube-controller-manager
    image: quay.io/coreos/hyperkube:v1.1.8_coreos.0
    command:
    - /hyperkube
    - controller-manager
    - --master=http://127.0.0.1:8080
    livenessProbe:
      httpGet:
        host: 127.0.0.1
        path: /healthz
        port: 10252
      initialDelaySeconds: 15
      timeoutSeconds: 1
EOF

# Configure kube-scheduler
cat << EOF > /srv/kubernetes/manifests/kube-scheduler.yaml
apiVersion: v1
kind: Pod
metadata:
  name: kube-scheduler
  namespace: kube-system
spec:
  hostNetwork: true
  containers:
  - name: kube-scheduler
    image: quay.io/coreos/hyperkube:v1.1.8_coreos.0
    command:
    - /hyperkube
    - scheduler
    - --master=http://127.0.0.1:8080
    livenessProbe:
      httpGet:
        host: 127.0.0.1
        path: /healthz
        port: 10251
      initialDelaySeconds: 15
      timeoutSeconds: 1
EOF

# Reload systemctl
systemctl daemon-reload

# Configure flannel network
curl -X PUT -d "value={\"Network\":\"$POD_NETWORK\",\"Backend\":{\"Type\":\"vxlan\"}}" "$ETCD_ENDPOINTS/v2/keys/coreos.com/network/config"

# Pre-fetch rkt images
rkt fetch quay.io/coreos/hyperkube:v1.1.8_coreos.0
# rkt fetch coreos.com/rkt/stage1-fly:1.1.0

# Start kubelet and wait for it to do its job
systemctl start kubelet
systemctl enable kubelet

# Do not reboot-strategy
echo "REBOOT_STRATEGY=off" >> /etc/coreos/update.conf
echo "Sleeping for 60 seconds to let kubelet do its job"
sleep 100

curl -H "Content-Type: application/json" -XPOST -d'{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"kube-system"}}' "http://127.0.0.1:8080/api/v1/namespaces" | echo "Not ready yet"

echo "Sleeping for 60 seconds to let kubelet do its job"
sleep 100

# Create kube-namespace
curl -H "Content-Type: application/json" -XPOST -d'{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"kube-system"}}' "http://127.0.0.1:8080/api/v1/namespaces" | echo "Already done"
