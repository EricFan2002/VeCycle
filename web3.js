const express = require('express');
const { ThorClient, HttpClient, VeChainPrivateKeySigner, VeChainProvider } = require("@vechain/sdk-network");
const { ethers, BigNumber } = require("ethers");
const { mnemonic, unitsUtils } = require("@vechain/sdk-core");
const { X2EarnRewardsPool, B3TR, VOT3, Treasury } = require("@vechain/vebetterdao-contracts");

const app = express();
app.use(express.json());

// User settings
const admin_addr = "equal toddler cube avocado service know bridge nest seminar mixed latin hidden";
const contractAddress = "0xbf64cf86894Ee0877C4e7d03936e35Ee8D8b864F";
const fromAddress = "0x762c5ff246dcc2a31a319bcc754e0d3874f8bd77";
const defaultPrivateKey = mnemonic.derivePrivateKey(admin_addr.split(' '));
console.log(defaultPrivateKey)
const APP_ID = "0x767308b4c9815c9fd756ad287379b26fa1af9c984490f969aca032da9de21a41";

const thorClient = new ThorClient(new HttpClient("https://testnet.vechain.org/"));
const xRewardPoolContract = thorClient.contracts.load(
    X2EarnRewardsPool.address.testnet,
    X2EarnRewardsPool.abi,
    new VeChainPrivateKeySigner(Buffer.from(defaultPrivateKey), new VeChainProvider(thorClient))
);

// const b3TR = thorClient.contracts.load(
//     B3TR.address.testnet,
//     B3TR.abi,
//     new VeChainPrivateKeySigner(Buffer.from(defaultPrivateKey), new VeChainProvider(thorClient))
// );

const vet = thorClient.contracts.load(
    Treasury.address.testnet,
    Treasury.abi,
    new VeChainPrivateKeySigner(Buffer.from(defaultPrivateKey), new VeChainProvider(thorClient))
);


async function distributeRewards(rewardMap) {
    const results = [];
    for (const [address, amount] of Object.entries(rewardMap)) {
        try {
            const amountInWei = unitsUtils.parseUnits(amount, 'ether');
            const receipt = await (await xRewardPoolContract.transact.distributeReward(
                APP_ID,
                amountInWei,
                address,
                "API Distribution"
            )).wait();
            results.push({ address, amount, status: 'success', txHash: receipt.transactionHash });
        } catch (error) {
            console.error(`Error distributing reward to ${address}:`, error);
            results.push({ address, amount, status: 'failed', error: error.message });
        }
    }
    return results;
}

app.post('/distribute-rewards', async (req, res) => {
    const rewardMap = req.body;

    if (!rewardMap || Object.keys(rewardMap).length === 0) {
        return res.status(400).json({ error: 'Invalid reward map' });
    }

    try {
        const results = await distributeRewards(rewardMap);
        res.json({ results });
    } catch (error) {
        console.error('Error processing reward distribution:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// New endpoint to check available funds for an app
app.get('/available-funds/:appId', async (req, res) => {
    let { appId } = req.params;

    try {
        // Convert appId to bytes32 if it's not already in that format
        if (!appId.startsWith('0x') || appId.length !== 66) {
            appId = ethers.utils.formatBytes32String(appId);
        }

        const convertWeiToVET = (wei) => {
            const weiBigNumber = BigInt(wei);
            const vetValue = Number(weiBigNumber) / Math.pow(10, 18); // VET uses 18 decimals
            return vetValue.toString(); // Return as a string for consistency
        };

        const availableFunds = await xRewardPoolContract.read.availableFunds(appId);
        const balance = await xRewardPoolContract.read.availableFunds(fromAddress);
        // const balance = await vet.read.balanceOf(fromAddress);
        // const balance = await vet.read.getVETBalance();
        // const balance = await vet.getVETBalance();

        res.json({
            appId,
            availableFunds: convertWeiToVET(availableFunds), // Convert Wei to VET
            availableB3TR: convertWeiToVET(balance)          // Convert balance from Wei to VET
        });
    } catch (error) {
        console.error('Error checking available funds:', error);
        res.status(500).json({ error: 'Internal server error', details: error.message });
    }
});

// New endpoint to deposit funds for an app
app.post('/deposit', async (req, res) => {
    const { amount, appId } = req.body;

    if (!amount || !appId) {
        return res.status(400).json({ error: 'Amount and appId are required' });
    }

    try {
        const amountInWei = unitsUtils.parseUnits(amount, 'ether');
        const receipt = await (await xRewardPoolContract.transact.deposit(amountInWei, appId)).wait();
        res.json({
            status: 'success',
            txHash: receipt.transactionHash,
            amount,
            appId
        });
    } catch (error) {
        console.error('Error depositing funds:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// New endpoint to withdraw funds for an app
app.post('/withdraw', async (req, res) => {
    const { amount, appId, reason } = req.body;

    if (!amount || !appId || !reason) {
        return res.status(400).json({ error: 'Amount, appId, and reason are required' });
    }

    try {
        const amountInWei = unitsUtils.parseUnits(amount, 'ether');
        const receipt = await (await xRewardPoolContract.transact.withdraw(amountInWei, appId, reason)).wait();
        res.json({
            status: 'success',
            txHash: receipt.transactionHash,
            amount,
            appId,
            reason
        });
    } catch (error) {
        console.error('Error withdrawing funds:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// New endpoint to get the B3TR token address
app.get('/b3tr-address', async (req, res) => {
    try {
        const b3trAddress = await xRewardPoolContract.read.b3tr();
        res.json({ b3trAddress });
    } catch (error) {
        console.error('Error getting B3TR address:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// New endpoint to get the X2EarnApps contract address
app.get('/x2earn-apps-address', async (req, res) => {
    try {
        const x2EarnAppsAddress = await xRewardPoolContract.read.x2EarnApps();
        res.json({ x2EarnAppsAddress });
    } catch (error) {
        console.error('Error getting X2EarnApps address:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});