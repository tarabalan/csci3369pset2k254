#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class k254PropShare(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(sorted(isect), n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.
        """
        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))

        # Calculate total download contributions from the previous round
        total_download = 0
        peer_contributions = {}
        
        if round > 0:  # Make sure it's not the first round
            last_round = history.downloads[-1]  # Get the previous round's downloads
            total_download = sum([download.blocks for download in last_round])
            for download in last_round:
                peer_contributions[download.from_id] = peer_contributions.get(download.from_id, 0) + download.blocks

        # Calculate the proportion of total download for each peer
        upload_shares = {}
        if total_download > 0:
            for peer_id, contribution in peer_contributions.items():
                upload_shares[peer_id] = contribution / total_download

        # Calculate proportional upload bandwidth for each peer
        total_upload = self.up_bw
        upload_bandwidths = {}

        for peer_id, share in upload_shares.items():
            upload_bandwidths[peer_id] = int(share * total_upload)

        # Reserve 10% of upload bandwidth for optimistic unblocking
        optimistic_bandwidth = int(total_upload * 0.1)
        total_upload -= optimistic_bandwidth  # Subtract this from the total bandwidth

        # Choose a random peer for optimistic unblocking
        if requests:
            chosen = [random.choice(requests).requester_id]  # Randomly select a peer
            bws = [optimistic_bandwidth]  # Give them the reserved bandwidth for optimistic unblocking
        else:
            chosen = []
            bws = []

        # Allocate remaining bandwidth proportionally to the peers
        remaining_peers = [peer_id for peer_id in upload_bandwidths.keys() if peer_id not in chosen]
        remaining_bandwidth = total_upload

        # Evenly distribute the remaining bandwidth
        if remaining_peers:
            remaining_bws = even_split(remaining_bandwidth, len(remaining_peers))
            chosen.extend(remaining_peers)
            bws.extend(remaining_bws)

        # Create Upload objects for the selected peers and their corresponding bandwidths
        uploads = [Upload(self.id, peer_id, bw) for peer_id, bw in zip(chosen, bws)]
        
        return uploads
