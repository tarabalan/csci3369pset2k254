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

class k254Tyrant(Peer):
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
        
        # Track peer download speeds based on past history
        peer_speeds = {peer.id: 0 for peer in peers}

        if history.current_round() > 0:
            last_round = history.downloads[-1]
            for download in last_round:
                peer_speeds[download.from_id] += download.blocks  # More blocks = faster peer

        # Sort peers by speed (fastest first)
        peers.sort(key=lambda p: peer_speeds.get(p.id, 0), reverse=True)

        # Count availability of each needed piece across all peers
        piece_counts = {}  # Dictionary to track how many peers have each piece
        for peer in peers:
            for piece in peer.available_pieces:
                if piece in np_set:  # Only count pieces that we actually need
                    piece_counts[piece] = piece_counts.get(piece, 0) + 1
            
        # Request pieces from peers
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)  # Pieces we need and peer has
            n = min(self.max_requests, len(isect))
        
            # Prioritize the rarest pieces, then by fastest responding peers
            for piece_id in sorted(isect, key=lambda p: (piece_counts[p], -peer_speeds.get(peer.id, 0)))[:n]:  
                start_block = self.pieces[piece_id]  # Next needed block
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            return []
        peer_contributions = {}

        
       
        if history.current_round() > 0:
            last_round = history.downloads[-1]  # Get the latest round’s downloads
            for download in last_round:
                peer_contributions[download.from_id] = peer_contributions.get(download.from_id, 0) + download.blocks

        # Prioritize peers who have contributed the most
        # Select top contributors
        # Adaptive bandwidth allocation - Increase allocation to top contributors
        peer_bandwidth_allocation = {peer_id: (peer_contributions[peer_id] / total_contribution) * self.up_bw for peer_id in sorted_peers}
        
        # Adjust for cases where we over-allocate
        scaling_factor = self.up_bw / sum(peer_bandwidth_allocation.values()) if sum(peer_bandwidth_allocation.values()) > 0 else 1
        
        bws = [int(peer_bandwidth_allocation[peer_id] * scaling_factor) for peer_id in chosen]

        
        # Occasionally unchoke a new peer with a small chance (exploration)
        if len(chosen) < self.max_requests and random.random() < 0.2:  # 20% chance
            new_peers = [r.requester_id for r in requests if r.requester_id not in chosen]
            if new_peers:
                new_peer = random.choice(new_peers)
                chosen.append(new_peer)
                bws.append(int(self.up_bw * 0.1))  # Give them a small fraction of bandwidth
        
        # Ensure bandwidth is fairly distributed
        if sum(bws) == 0:
            chosen = [r.requester_id for r in random.sample(requests, min(len(requests), self.max_requests))]
            bws = even_split(self.up_bw, len(chosen))
        
        uploads = [Upload(self.id, peer_id, bw) for peer_id, bw in zip(chosen, bws)]
        return uploads

