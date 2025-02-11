import random
import logging

from messages import Upload, Request
from peer import Peer

class k254Tourney(Peer):
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
        # np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        piece_counts = {}

        # Count availability of each piece
        for peer in peers:
            for piece in peer.available_pieces:
                if piece in needed_pieces:
                    piece_counts[piece] = piece_counts.get(piece, 0) + 1

        # Sort needed pieces by rarity
        rarest_pieces = sorted(piece_counts, key=lambda p: piece_counts[p])

        # Prioritize completing partially downloaded pieces
        partially_downloaded = [
            (piece, self.conf.blocks_per_piece - self.pieces[piece])
            for piece in needed_pieces
        ]
        partially_downloaded.sort(key=lambda x: x[1])  # Fewest remaining blocks first

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...

        # improved peer sort
        peers.sort(key=lambda p: p.id)

        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(set(rarest_pieces))
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

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        #track contributions from previous rounds
        last_round_downloads = history.downloads[round-1] if round > 0 else []
        contributions = {}
        for dl in last_round_downloads:
            if dl.from_id in contributions:
                contributions[dl.from_id] += dl.blocks
            else:
                contributions[dl.from_id] = dl.blocks    

        total_contributions = sum(contributions.values())
        if total_contributions == 0:
            total_contributions = 1  # Prevent division by zero

        # Allocate bandwidth proportionally based on contributions
        proportional_bw = int(self.up_bw * 0.93)
        optimistic_bw = self.up_bw - proportional_bw
        
        top_contributors = sorted(contributions, key=contributions.get, reverse=True)[:3]
        
        bws = []
        chosen = []

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            optimistic_peer = random.choice(peers).id
            chosen = [optimistic_peer]
            bws = [optimistic_bw]  # All bandwidth goes to the optimistic peer
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            for requester_id in top_contributors:
                share = (contributions[requester_id] / total_contributions) * proportional_bw
                bws.append(int(share))
                chosen.append(requester_id)
            # Add optimistic peer
            remaining_requesters = [r.requester_id for r in requests if r.requester_id not in chosen]
            if remaining_requesters:
                optimistic_peer = random.choice(remaining_requesters)
                chosen.append(optimistic_peer)
                bws.append(optimistic_bw)

        # Normalize bandwidth allocation
        total_allocated = sum(bws)
        if total_allocated < self.up_bw:
            bws[-1] += self.up_bw - total_allocated
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
