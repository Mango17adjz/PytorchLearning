from __future__ import print_function
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.optim.lr_scheduler import StepLR


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        # 卷积层，输入通道1，输出通道32，卷积核3*3，步长1 (28*28-->26*26)
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        # 卷积层，输入通道32，输出通道64，卷积核3*3，步长1 (26*26-->24*24)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        # droupout层，防止过拟合，丢弃率25%
        self.dropout1 = nn.Dropout(0.25)
        # droupout层，丢弃率50%
        self.dropout2 = nn.Dropout(0.5)
        # 全连接层，，输入特征数为9216，输出特征数为128 (12*12*64=9216)
        self.fc1 = nn.Linear(9216, 128)
        # 全连接层，，输入特征数为128，输出特征数为10
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)  # ReLU激活函数，进行非线性变换 max(0,x)
        x = self.conv2(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)  # 2*2最大池化 (24*24-->12*12)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)  # 将特征图展平成一维张量
        x = self.fc1(x)
        x = F.relu(x)
        x = self.dropout2(x)
        x = self.fc2(x)
        output = F.log_softmax(x, dim=1)  # log_softmax取对数操作解决了softmax的溢出问题
        return output


def train(args, model, device, train_loader, optimizer, epoch):
    model.train()  # 模型设置为训练模式
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()  # 清除优化器中之前批次的梯度
        output = model(data)  # 前向传播
        loss = F.nll_loss(output, target)  # 负对数似然损失
        loss.backward()  # 反向传播，计算梯度
        optimizer.step()  # 更新参数
        if batch_idx % args.log_interval == 0:
            # 打印训练日志，包括当前训练轮数、已处理样本数、总样本数、完成进度、损失值
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))
            if args.dry_run:
                break


def test(model, device, test_loader):
    model.eval()  # 模型设置为评估模式
    test_loss = 0
    correct = 0
    with torch.no_grad():  # 关闭梯度计算，节省运算资源
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += F.nll_loss(output, target, reduction='sum').item()  # sum up batch loss
            pred = output.argmax(dim=1, keepdim=True)  # get the index of the max log-probability
            # 比较预测值和真实值，并得到预测正确的样本总数。view_as确保target和pred形状相同
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)  # 计算平均测试损失

    print('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, correct, len(test_loader.dataset),
        100. * correct / len(test_loader.dataset)))  # 打印评估结果


def main():
    # Training settings
    parser = argparse.ArgumentParser(description='PyTorch MNIST Example')
    parser.add_argument('--batch-size', type=int, default=64, metavar='N',
                        help='input batch size for training (default: 64)')
    parser.add_argument('--test-batch-size', type=int, default=1000, metavar='N',
                        help='input batch size for testing (default: 1000)')
    parser.add_argument('--epochs', type=int, default=14, metavar='N',
                        help='number of epochs to train (default: 14)')
    parser.add_argument('--lr', type=float, default=1.0, metavar='LR',
                        help='learning rate (default: 1.0)')
    parser.add_argument('--gamma', type=float, default=0.7, metavar='M',
                        help='Learning rate step gamma (default: 0.7)')
    parser.add_argument('--no-cuda', action='store_true', default=False,
                        help='disables CUDA training')
    parser.add_argument('--no-mps', action='store_true', default=False,
                        help='disables macOS GPU training')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='quickly check a single pass')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')
    parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status')
    parser.add_argument('--save-model', action='store_true', default=False,
                        help='For Saving the current Model')
    args = parser.parse_args()
    use_cuda = not args.no_cuda and torch.cuda.is_available()
    use_mps = not args.no_mps and torch.backends.mps.is_available()

    torch.manual_seed(args.seed)

    if use_cuda:
        device = torch.device("cuda")
    elif use_mps:
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    train_kwargs = {'batch_size': args.batch_size}
    test_kwargs = {'batch_size': args.test_batch_size}
    if use_cuda:
        cuda_kwargs = {'num_workers': 1,
                       'pin_memory': True,
                       'shuffle': True}
        train_kwargs.update(cuda_kwargs)
        test_kwargs.update(cuda_kwargs)

    # 数据预处理，将图像转换为张量并进行标准化
    transform=transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))  # 均值0.1307，标准差0.3081
        ])
    # 训练集
    dataset1 = datasets.MNIST('../data', train=True, download=True,
                       transform=transform)
    # 测试集
    dataset2 = datasets.MNIST('../data', train=False,
                       transform=transform)
    # 数据加载器
    train_loader = torch.utils.data.DataLoader(dataset1,**train_kwargs)
    test_loader = torch.utils.data.DataLoader(dataset2, **test_kwargs)

    # 创建模型Net实例和优化器Adadelta
    model = Net().to(device)
    optimizer = optim.Adadelta(model.parameters(), lr=args.lr)

    # 创建学习率调度器StepLR，用于调整学习率。1epoch调整一次学习率，学习率更新为原来的gamma倍
    scheduler = StepLR(optimizer, step_size=1, gamma=args.gamma)

    # 迭代训练和评估过程，每周期一次训练和评估
    for epoch in range(1, args.epochs + 1):
        train(args, model, device, train_loader, optimizer, epoch)
        test(model, device, test_loader)
        scheduler.step()

    if args.save_model:
        torch.save(model.state_dict(), "mnist_cnn.pt")


if __name__ == '__main__':
    main()
