###
# Copyright (c) 2012, Benjamin Rubin
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

from supybot.commands import wrap
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy import API
from tweepy.streaming import StreamListener
import urlparse
import htmllib
import threading
import httplib

class IRCStream(StreamListener):
    def on_status(self, status):
        try:
            self.plugin._announce(status)
        except AttributeError:
            pass

    def on_limit(self, track):
        self.plugin.log.warn('IRCStream Limit: %s' % track)

    def on_error(self, status):
        self.plugin.log.warn('IRCStream Error: %s' % status)

    def on_timeout(self):
        self.plugin.log.warn('IRCStream Timeout')

    def set_tweets(self, t):
        self.plugin = t


def unencode(s):
    p = htmllib.HTMLParser(None)
    p.save_bgn()
    p.feed(s)
    return p.save_end().encode('utf-8', 'replace')


class Supytwit(callbacks.Plugin):
    """Add the help for "@plugin help Supytwit" here
    This should describe *how* to use this plugin."""
#    callbacks.threaded = True
#    threaded = True
    callbefore = ['URL']

    def __init__(self, irc):
        self.__parent = super(Supytwit, self)
        self.__parent.__init__(irc)
        self.irc = irc
        self.t = None

        try:
            self.announce_channel = self.registryValue('announce_channel')
            self.consumer_key = self.registryValue('consumer_key')
            self.consumer_secret = self.registryValue('consumer_secret')
            self.access_token = self.registryValue('access_token')
            self.access_token_secret = self.registryValue('access_token_secret')
        except AttributeError:
            irc.error('Please ensure that all config values for Supytwit have been set')
            return

        if '' in [self.consumer_key, self.consumer_secret, self.access_token,
                self.access_token_secret]:
            irc.error('Please ensure that all the registry values are set for Supytwit')
            return

        self.auth = self._auth(self.consumer_key, self.consumer_secret, self.access_token,
                               self.access_token_secret)
        self.api = API(self.auth)

        self.streamListener = IRCStream()
        self.streamListener.set_tweets(self)
        self.e = threading.Event()


    def status(self, irc, msg, args):
        self.log.info(','.join([str(thread) for thread in
            threading.enumerate()]))


    def start(self, irc, msg, args):
        """Start the thread"""
        self.log.info(', '.join([t.name for t in threading.enumerate()]))
        if filter(lambda x: x.name == 'SupytwitMonitor',
                threading.enumerate()):
            return
        self.e.clear()
        self.t = threading.Thread(target=self._monitor, name='SupytwitMonitor')
        self.t.start()
    start = wrap(start)

    def stop(self, irc, msg, args):
        """Stop the thread"""
        try:
            self.stream.disconnect()
        except AttributeError:
            pass
    stop = wrap(stop)

    def die(self):
        self.stream.disconnect()
        self.__parent.die()

    def _monitor(self):
        self.stream = Stream(self.auth, self.streamListener, async=True)
        while True:
            try:
                self.stream.userstream()
            except httplib.IncompleteRead:
                pass

    def _auth(self, c_key, c_secret, a_token, a_secret):
        auth = OAuthHandler(c_key, c_secret)
        auth.set_access_token(a_token, a_secret)
        return auth


    def _announce(self, status):
        if hasattr(status, 'retweeted_status'):
            rt = status.retweeted_status
            text = 'RT @%s: %s' % (rt.author.screen_name, rt.text)
        else:
            text = status.text
        msg = '@%s: %s' % (ircutils.bold(status.author.screen_name), text)
        self.irc.queueMsg(ircmsgs.privmsg(self.announce_channel, unencode(msg)))

    def _print(self, status):
        self.log.info('@%s: %s' % (status.author.screen_name, status.text))

    def parseStatusId(self, message):
        for word in message.split(' '):
            if word.find('//twitter.com/') != -1:
                try:
                    id = filter(lambda x: x != '', urlparse.urlsplit(word).path.split('/'))[-1]
                except IndexError:
                    return None
                return id

    def doPrivmsg(self, irc, msg):
        if msg.args[1].find("//twitter.com/") != -1:
            id = self.parseStatusId(msg.args[1])
            self.log.info(id)
            try:
                status = self.api.get_status(id)
            except tweepy.TweepError:
                pass
            author = status.author.screen_name
            
            if hasattr(status, 'retweeted_status'):
                rt = status.retweeted_status
                text = 'RT @%s: %s' % (rt.author.screen_name, rt.text)
            else:
                text = status.text.replace('\n', ' ')
            message = '@%s: %s' % (ircutils.bold(author), text)
            self.log.info(message)
            irc.queueMsg(ircmsgs.privmsg(msg.args[0], unencode(message)))


Class = Supytwit


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
