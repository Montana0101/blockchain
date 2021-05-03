# {
#     "index":0,  # 块索引
#     'timestamp':'',  # 时间戳
#     'transcations':[  # 交易信息(多个交易)
#         {
#             'sender':'',
#             'recipient':'',
#             'amount':'0.77btc'
#         }
#     ],
#     'proof':'',  # 工作量证明
#     'previous_hash':''  # 上个区块哈希
# }
import time
import hashlib
import json
import uuid
import requests

from flask import Flask, jsonify, request
from urllib.parse import urlparse
from argparse import ArgumentParser


class Blockchain:
    def __init__(self, *args, **kwargs):
        self.chain = []  # 链
        self.current_transcations = []  # 当前交易信息
        self.nodes = set([])  # 节点
        self.new_block(proof=100, previous_hash=1)  # 创世块

    def register_node(self, address: str):  # 注册节点
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)

    def new_block(self, proof, previous_hash=None):  # 新区块
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transcations': self.current_transcations,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block)
        }
        self.current_transcations = []
        self.chain.append(block)
        return block

    def new_transcation(self, sender, recipient, amount):  # 新交易
        self.current_transcations.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):  # 计算区块的哈希值
        block_string = json.dumps(block, sort_keys=True).encode()
        return (hashlib.sha256(block_string)).hexdigest()

    @property
    def last_block(self):  # 获取区块链最后一个块
        return self.chain[-1]

    def work_proof(self, last_proof):  # 工作量证明
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    def valid_proof(self, last_proof: int, proof: int):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[0:4] == '0000'

    def valid_chain(self, chain):
        last_block = chain[0]
        current_inx = 1
        while current_inx < len(chain):
            block = chain[current_inx]

            if block['previous_hash'] != self.hash(last_block):
                return False
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_inx += 1

        return True

    def resolve_conflict(self):  # 解决冲突
        neighbours = self.nodes
        max_length = len(self.chain)
        new_chain = None

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['total']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False


blockchain = Blockchain()
app = Flask(__name__)
node_identifier = str(uuid.uuid4()).replace('-', '')


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {'chain': blockchain.chain, 'total': len(blockchain.chain)}
    return jsonify(response), 200


@app.route('/transcation/new', methods=['POST'])
def new_transcation():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if values is None:
        return "can't be empty", 400
    if not all(k in values for k in required):
        return 'missing required parameters', 400
    index = blockchain.new_transcation(values['sender'], values['recipient'],
                                       values['amount'])
    return jsonify({'message':
                    f'Transcation will be added to Block {index}'}), 201


@app.route('/mining', methods=['POST'])
def mining():  # 挖矿方法
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.work_proof(last_proof)  # 计算当前工作量

    blockchain.new_transcation(sender="0", recipient=node_identifier, amount=1)
    block = blockchain.new_block(proof, None)

    response = {
        "message": 'new block forged',
        'index': block['index'],
        "transcations": block['transcations'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }

    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():  # 注册节点
    values = request.get_json()
    if values is None:
        return 'Error : can not be empty', 400
    nodes = values.get('nodes')
    for node in nodes:
        blockchain.register_node(node)

    response = {
        "message": 'New nodes have been added',
        "total_nodes": list(blockchain.nodes)
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    isReplaced = blockchain.resolve_conflict()
    if isReplaced:
        response = {
            'message': 'chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'chain is authority',
            'new_chain': blockchain.chain
        }
    return jsonify(response), 200


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p',
                        '--port',
                        default=5000,
                        type=int,
                        help='listen to port ')
    args = parser.parse_args()
    port = args.port

    app.run('0.0.0.0', port)
