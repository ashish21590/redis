#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <sys/time.h>
#include <signal.h>

#include "ae.h"
#include "anet.h"
#include "sds.h"

#define REPLY_INT 0
#define REPLY_RETCODE 1
#define REPLY_BULK 2

#define CLIENT_CONNECTING 0
#define CLIENT_SENDQUERY 1
#define CLIENT_READREPLY 2

#define MAX_LATENCY 5000

static struct config {
    int clients;
    int requests;
    int liveclients;
    int donerequests;
    int keysize;
    int datasize;
    aeEventLoop *el;
    char *hostip;
    int hostport;
    int keepalive;
    long long start;
    long long totlatency;
    int *latency;
} config;

typedef struct _client {
    int state;
    int fd;
    sds obuf;
    sds ibuf;
    int readlen;        /* readlen == -1 means read a single line */
    unsigned int written;        /* bytes of 'obuf' already written */
    int replytype;
    long long start;    /* start time in milliseconds */
} *client;

/* Prototypes */
static void writeHandler(aeEventLoop *el, int fd, void *privdata, int mask);
static void createMissingClients(client c);

/* Implementation */
static long long mstime(void) {
    struct timeval tv;
    long long mst;

    gettimeofday(&tv, NULL);
    mst = ((long)tv.tv_sec)*1000;
    mst += tv.tv_usec/1000;
    return mst;
}

static void freeClient(client c) {
    aeDeleteFileEvent(config.el,c->fd,AE_WRITABLE);
    aeDeleteFileEvent(config.el,c->fd,AE_READABLE);
    sdsfree(c->ibuf);
    sdsfree(c->obuf);
    close(c->fd);
    free(c);
    config.liveclients--;
}

static void resetClient(client c) {
    aeDeleteFileEvent(config.el,c->fd,AE_WRITABLE);
    aeDeleteFileEvent(config.el,c->fd,AE_READABLE);
    aeCreateFileEvent(config.el,c->fd, AE_WRITABLE,writeHandler,c,NULL);
    sdsfree(c->ibuf);
    c->ibuf = sdsempty();
    c->readlen = 0;
    c->written = 0;
    c->state = CLIENT_SENDQUERY;
    c->start = mstime();
}

static void clientDone(client c) {
    long long latency;
    config.donerequests ++;
    latency = mstime() - c->start;
    if (latency > MAX_LATENCY) latency = MAX_LATENCY;
    config.latency[latency]++;

    if (config.donerequests == config.requests) {
        freeClient(c);
        aeStop(config.el);
        return;
    }
    if (config.keepalive) {
        resetClient(c);
    } else {
        config.liveclients--;
        createMissingClients(c);
        config.liveclients++;
        freeClient(c);
    }
}

static void readHandler(aeEventLoop *el, int fd, void *privdata, int mask)
{
    char buf[1024];
    int nread;
    client c = privdata;

    nread = read(c->fd, buf, 1024);
    if (nread == -1) {
        fprintf(stderr, "Reading from socket: %s\n", strerror(errno));
        freeClient(c);
        return;
    }
    if (nread == 0) {
        fprintf(stderr, "EOF from client\n");
        freeClient(c);
        return;
    }
    c->ibuf = sdscatlen(c->ibuf,buf,nread);

    if (c->replytype == REPLY_INT ||
        c->replytype == REPLY_RETCODE ||
        (c->replytype == REPLY_BULK && c->readlen == -1)) {
        char *p;

        if ((p = strchr(c->ibuf,'\n')) != NULL) {
            if (c->replytype == REPLY_BULK) {
                *p = '\0';
                *(p-1) = '\0';
                c->readlen = atoi(c->ibuf)+2;
                c->ibuf = sdsrange(c->ibuf,(p-c->ibuf)+1,-1);
            } else {
                c->ibuf = sdstrim(c->ibuf,"\r\n");
                clientDone(c);
                return;
            }
        }
    }
    /* bulk read */
    if ((unsigned)c->readlen == sdslen(c->ibuf))
        clientDone(c);
}

static void writeHandler(aeEventLoop *el, int fd, void *privdata, int mask)
{
    client c = privdata;

    if (c->state == CLIENT_CONNECTING) {
        c->state = CLIENT_SENDQUERY;
        c->start = mstime();
    }
    if (sdslen(c->obuf) > c->written) {
        void *ptr = c->obuf+c->written;
        int len = sdslen(c->obuf) - c->written;
        int nwritten = write(c->fd, ptr, len);
        if (nwritten == -1) {
            fprintf(stderr, "Writing to socket: %s\n", strerror(errno));
            freeClient(c);
            return;
        }
        c->written += nwritten;
        if (sdslen(c->obuf) == c->written) {
            aeDeleteFileEvent(config.el,c->fd,AE_WRITABLE);
            aeCreateFileEvent(config.el,c->fd,AE_READABLE,readHandler,c,NULL);
            c->state = CLIENT_READREPLY;
        }
    }
}

static client createClient(void) {
    client c = malloc(sizeof(struct _client));
    char err[ANET_ERR_LEN];

    c->fd = anetTcpNonBlockConnect(err,config.hostip,config.hostport);
    if (c->fd == ANET_ERR) {
        free(c);
        fprintf(stderr,"Connect: %s\n",err);
        return NULL;
    }
    c->obuf = sdsempty();
    c->ibuf = sdsempty();
    c->readlen = 0;
    c->written = 0;
    c->state = CLIENT_CONNECTING;
    aeCreateFileEvent(config.el, c->fd, AE_WRITABLE, writeHandler, c, NULL);
    config.liveclients++;
    return c;
}

static void createMissingClients(client c) {
    while(config.liveclients < config.clients) {
        client new = createClient();
        if (!new) continue;
        sdsfree(new->obuf);
        new->obuf = sdsdup(c->obuf);
        new->replytype = c->replytype;
    }
}

static void showLatencyReport() {
    int j, seen = 0;
    float perc;

    printf("== %d requests completed in %.2f seconds\n", config.donerequests,
        (float)config.totlatency/1000);
    printf("== %d parallel clients\n", config.clients);
    printf("== keep alive: %d\n", config.keepalive);
    printf("\n");
    for (j = 0; j <= MAX_LATENCY; j++) {
        if (config.latency[j]) {
            seen += config.latency[j];
            perc = ((float)seen*100)/config.donerequests;
            printf("%.2f%% <= %d milliseconds\n", perc, j);
        }
    }
    printf("\n== %.2f requests per second\n", (float)config.donerequests/((float)config.totlatency/1000));
}

int main(int argc, char **argv) {
    client c;

    signal(SIGHUP, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);

    config.clients = 50;
    config.requests = 100000;
    config.liveclients = 0;
    config.el = aeCreateEventLoop();
    config.keepalive = 1;
    config.donerequests = 0;

    config.hostip = "127.0.0.1";
    config.hostport = 6379;

    if (config.keepalive == 0) {
        printf("WARNING: keepalive disabled, you probably need 'echo 1 > /proc/sys/net/ipv4/tcp_tw_reuse' in order to use a lot of clients/requests\n");
    }

    /* Write test */
    config.latency = malloc(sizeof(int)*(MAX_LATENCY+1));
    memset(config.latency,0,sizeof(int)*(MAX_LATENCY+1));
    config.start = mstime();

    c = createClient();
    if (!c) exit(1);
    c->obuf = sdscat(c->obuf,"SET foo 3\r\nbar\r\n");
    c->replytype = REPLY_RETCODE;
    createMissingClients(c);
    aeMain(config.el);
    config.totlatency = mstime()-config.start;

    showLatencyReport();
    return 0;
}
