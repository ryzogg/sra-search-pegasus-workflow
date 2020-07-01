FROM ubuntu:18.04

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libbz2-dev \
    liblzma-dev \
    libxml-libxml-perl \
    locales \
    python \
    python3 \
    unzip \
    wget \
    zlib1g-dev
    
RUN locale-gen en_US.UTF-8

# sratoolkit
RUN wget -nv https://ftp-trace.ncbi.nlm.nih.gov/sra/sdk/2.10.0/sratoolkit.2.10.0-ubuntu64.tar.gz -O /tmp/sratoolkit.tar.gz \
    && tar zxvf /tmp/sratoolkit.tar.gz -C /opt/ \
    && mv /opt/sratoolkit.2.10.0-ubuntu64 /opt/sratoolkit-2.10.0 \
    && rm -f /tmp/sratoolkit.tar.gz

# bowtie2
RUN wget -nv https://github.com/BenLangmead/bowtie2/releases/download/v2.2.9/bowtie2-2.2.9-linux-x86_64.zip -O /tmp/bowtie2-2.2.9-linux-x86_64.zip \
    && unzip /tmp/bowtie2-2.2.9-linux-x86_64.zip -d /opt/ \
    && rm -f /tmp/bowtie2-2.2.9-linux-x86_64.zip
    
# samtools
RUN wget -nv https://github.com/samtools/samtools/releases/download/1.10/samtools-1.10.tar.bz2 -O /tmp/samtools-1.10.tar.bz2 \
    && tar xjf /tmp/samtools-1.10.tar.bz2 -C /tmp/ \
    && ls -l /tmp/ \
    && cd /tmp/samtools-1.10 \
    && ./configure --prefix=/opt/samtools-1.10 --without-curses \
    && make install \
    && cd /tmp \
    && rm -rf /tmp/samtools-1.10.tar.bz2 /tmp/samtools-1.10

ENV PATH="/opt/sratoolkit-2.10.0/bin:/opt/bowtie2-2.2.9:/opt/samtools-1.10/bin:${PATH}"


