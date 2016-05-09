#!/bin/bash

while getopts "m:" OPTION
do
    case $OPTION in
        m)
          MASTER=$OPTARG
          ;;
        ?)
          exit
          ;;
    esac
done

ADVERTISE_IP=`ifconfig eth0 | grep 'inet ' | cut -d: -f2 | awk '{ print $2}'`
POD_NETWORK=10.2.0.0/16
SERVICE_IP_RANGE=10.3.0.0/24
K8S_SERVICE_IP=10.3.0.1
DNS_SERVICE_IP=10.3.0.10
ETCD_ENDPOINTS=http://${MASTER}:2379
K8S_VER=v1.1.8_coreos.0

# Prepare kubelet of master server
mkdir -p /etc/kubernetes/manifests
mkdir -p /srv/kubernetes/manifests

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
  --api-servers=http://${MASTER}:8080 \
  --register-node=true \
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

# Configure proxy
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
    - --master=http://${MASTER}:8080
    - --proxy-mode=iptables
    securityContext:
      privileged: true
EOF

systemctl daemon-reload
systemctl start kubelet
systemctl enable kubelet

echo "REBOOT_STRATEGY=off" >> /etc/coreos/update.conf

